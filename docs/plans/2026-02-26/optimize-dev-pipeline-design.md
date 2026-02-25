# Design: Dev Pipeline Optimization (< 2 min)

## 1. Goal
Reduce the total execution time of `.github/workflows/dev.yml` from ~8 minutes to under 2 minutes.

## 2. Architecture Changes

### 2.1. Workflow Parallelization
Currently, the pipeline runs sequentially: `lint` & `test` -> `build` -> `deploy`. 
We will change this to run `lint`, `test`, and `build` in parallel.

- **Jobs**:
    - `lint`: Runs independently.
    - `test`: Runs independently (requires Postgres service).
    - `build`: Runs independently.
    - `deploy`: Depends on `[lint, test, build]`.
- **Benefit**: Removes ~2-3 minutes of sequential waiting time.

### 2.2. Dockerfile Optimization (Model Layer Isolation)
The `SentenceTransformer` model (~1GB) is currently downloaded after `uv sync`. Any change in `uv.lock` invalidates the model download layer.

- **Changes**:
    1. Create a `model-downloader` stage in `Dockerfile`.
    2. This stage only depends on a specific version/name of the model.
    3. Use `COPY --from=model-downloader` in the main builder stage.
- **Benefit**: Model download happens ONLY when the model name changes, not when dependencies or source code change. This saves ~3-4 minutes of download/processing time during build.

### 2.3. Caching Enhancements
- Keep using `type=gha` cache with `mode=max` in `docker/build-push-action`.
- Ensure `uv` cache is utilized where possible.

## 3. Success Criteria
- Total workflow duration < 2 minutes on subsequent runs (when cache is warm).
- Deployment only triggers if all validation (lint, test) and build succeed.

## 4. Risks & Mitigations
- **Concurrent Resource Usage**: Running 3 jobs at once uses more GHA minutes, but reduces wall-clock time.
- **Cache Size**: The 1GB model will take up cache space, but GHA allows up to 10GB per repo.
