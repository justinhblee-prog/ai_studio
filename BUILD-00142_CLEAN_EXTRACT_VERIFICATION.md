# BUILD-00142 Clean Extraction Verification

The release ZIP was extracted into a new directory with no dependency installation or source-tree reuse. Checks were run from the extracted package.

| Check | Result |
|---|---:|
| Backend full pytest | 361 passed |
| Python compileall | PASS |
| Viewer structural source checks | 140 passed |
| TypeScript syntax/transpilation | 10 source + 4 declaration parses, 0 errors |
| Viewer API contract | 64/64 matched |
| Request body contract | 15 checked, 0 findings |
| Response contract | 52 JSON / 53 endpoints / 29 models, 0 missing |
| Package integrity | 0 findings |

The clean extraction also contains the same authenticated download path and cleanup observability implementation as the source tree. Semantic TypeScript typecheck and actual React/Three.js component E2E remain blocked/unverified as described in the main verification report.
