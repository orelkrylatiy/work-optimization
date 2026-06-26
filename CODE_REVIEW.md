# Code Review: hh-applicant-tool AI Integration

## Summary
Changes add AI-powered employer chat replies (`reply-employers --use-ai`), local prompt files, LLM setup docs, and minor fixes.

## ✅ What's Good

1. **`get_reply_ai()` method** — Clean separation of concerns, follows existing `get_cover_letter_ai()` pattern
2. **`load_prompt()` utility** — Flexible resolution (@file, path, inline), well-documented
3. **Fallback logic** — `openai_reply` → `openai_cover_letter` is pragmatic
4. **`timedelta` fix** — `scheduler.py` month/year boundary bug fixed correctly
5. **Documentation** — `LLM_SETUP.md` provides comprehensive setup guide

## ⚠️ Issues Found

### 1. CRITICAL: Ollama URL 404 Error (Not Fixed)
**File:** `src/hh_applicant_tool/ai/base.py` (not shown in diff)

**Problem:** Error shows `http://localhost:11434/v1/chat/completions` returns 404.

**Root Cause:** Ollama's OpenAI-compatible endpoint is at `/v1/chat/completions` **only for specific models**. The base URL may need `/api/generate` for native Ollama API, or the model name is wrong.

**Fix Required:**
```python
# Check if Ollama is running native or OpenAI mode
# Native: http://localhost:11434/api/generate
# OpenAI compat: http://localhost:11434/v1/chat/completions
```

**Action:** Verify Ollama configuration and update `base_url` in config.

---

### 2. HIGH: No Validation in `load_prompt()`
**File:** `src/hh_applicant_tool/utils/misc.py`

**Problem:** If file path doesn't exist (and doesn't start with `@`), silently returns the path as string. This causes confusing errors later.

**Current:**
```python
if candidate.is_file():
    return candidate.read_text(...)
return value  # ← Could be a typo'd path!
```

**Fix:**
```python
if candidate.is_file():
    return candidate.read_text(...)
elif Path(value).expanduser().exists():
    # It exists but isn't a file (directory?)
    raise ValueError(f"Prompt path is not a file: {value}")
# Treat as inline prompt
return value
```

---

### 3. MEDIUM: `reply_ai` Fallback is Silent
**File:** `src/hh_applicant_tool/operations/reply_employers.py:126-131`

**Problem:** If both `openai_reply` and `openai_cover_letter` configs are missing, `self.reply_ai` becomes `None` silently. Later code checks `elif self.reply_ai:` but user gets no warning.

**Fix:**
```python
if self.reply_ai is None and args.use_ai:
    logger.warning(
        "AI requested but neither 'openai_reply' nor 'openai_cover_letter' "
        "configured. Falling back to template messages."
    )
```

---

### 4. MEDIUM: No Rate Limiting on `reply_ai`
**File:** `src/hh_applicant_tool/operations/reply_employers.py`

**Problem:** `get_reply_ai()` creates client without explicit rate limit. `reply_iterative_ai.py` has manual 2s pauses, but `reply-employers --use-ai` CLI command doesn't.

**Risk:** Ollama/OpenAI rate limits if processing 50+ chats quickly.

**Fix:** Set `rate_limit` in config or add delay in loop:
```python
# In _reply_to_negotiation() loop
if self.reply_ai:
    time.sleep(1.0)  # Rate limiting
```

---

### 5. LOW: `test_ai_letter.py` Should Be in `tests/`
**File:** `test_ai_letter.py` (root)

**Problem:** Test file in project root, not in `tests/` directory. Won't be picked up by `pytest`.

**Fix:** Move to `tests/test_ai_letter.py` or delete after use.

---

### 6. LOW: `.nessy/settings.json` Changes
**File:** `.nessy/settings.json`

**Problem:** IDE/tool-specific settings committed. These should be in `.gitignore` or user-local.

**Fix:** Add `.nessy/` to `.gitignore` (keep `.nessy/output-language.md` if needed).

---

### 7. LOW: Deleted Prompt Files
**Files:** `prompts/*.md` deleted

**Problem:** Old `.prompt` and `.md` files deleted but `prompts/README.md` may still reference them.

**Action:** Verify `prompts/README.md` is updated.

---

## 🔧 Recommended Fixes (Priority Order)

1. **Fix Ollama endpoint** — Verify `base_url` and model name
2. **Add validation to `load_prompt()`** — Fail fast on bad paths
3. **Add warning for missing AI config** — Help users debug
4. **Add rate limiting** — Prevent API throttling
5. **Move/delete test file** — Clean up project root
6. **Update .gitignore** — Exclude `.nessy/settings.json`

---

## Security Review

✅ No secrets exposed in diff
✅ No new external dependencies
✅ File reads use `expanduser()` (safe)
⚠️ `load_prompt()` could read arbitrary files if user passes malicious path — but this is user-controlled input, acceptable risk

---

## Testing Gaps

- No unit tests for `load_prompt()`
- No integration test for `reply-employers --use-ai`
- No test for fallback chain (`openai_reply` → `openai_cover_letter`)

**Recommended:**
```python
# tests/test_prompt_loading.py
def test_load_prompt_inline(): assert load_prompt("test") == "test"
def test_load_prompt_file(): assert load_prompt("@path/to/file.txt") == "..."
def test_load_prompt_missing(): pytest.raises(...)
```

---

## Final Verdict

**Status:** ✅ Ready to merge with minor fixes

**Must-fix before production:**
1. Ollama endpoint configuration
2. `load_prompt()` validation

**Nice-to-have:**
3. Warning for missing AI config
4. Rate limiting
5. Test coverage

**Overall Quality:** 7/10 — Solid foundation, needs polish on error handling and validation.
