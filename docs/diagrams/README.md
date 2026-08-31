# Diagrams

Source and rendered versions of the diagrams used in the docs.

```
diagrams/
├── src/        # Mermaid source (.mmd) — edit these
└── rendered/   # Exported SVGs — regenerate after editing src
```

Each file pairs by name: `src/algorithm-overview.mmd` renders to
`rendered/algorithm-overview.svg`.

| Diagram (`src` / `rendered` basename) | Algorithm type | Used in |
|---|---|---|
| `algorithm-overview` | Greedy single-pass heuristic (current) | [route-finding.md](../route-finding.md), [algorithm-analysis.md](../algorithm-analysis.md) |
| `approach-1-classical` | Classical constrained optimization (1a library / 1b custom SA) | [algorithm-analysis.md](../algorithm-analysis.md) |
| `approach-2-pure-ai` | Pure AI (LLM builds the whole itinerary; layered validation) | [algorithm-analysis.md](../algorithm-analysis.md) |
| `approach-3-hybrid` | Hybrid (AI generation + validation loop + optimizer; 3a library / 3b custom) | [algorithm-analysis.md](../algorithm-analysis.md) |

## Tooling

Scripts and dependencies live here in `docs/diagrams/`. Install once:

```bash
# From docs/diagrams/
npm install
```

### Validating

`validate.mjs` parses every `.mmd` source **and** every inline ```mermaid```
block in the sibling markdown docs, failing (non-zero exit) if any diagram is
malformed — so it works locally and in CI:

```bash
npm run validate
```

### Regenerating the SVGs

Rendered SVGs are produced with
[`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli):

```bash
npm run render
```

Each file pairs by name — `src/<name>.mmd` renders to `rendered/<name>.svg`. The
markdown docs embed the diagrams as inline ```mermaid``` blocks (GitHub renders
those natively), so re-rendering is only needed to keep the standalone SVG files
in sync.
