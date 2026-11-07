# Fonts in claude-violet

All fonts here are under the SIL Open Font License 1.1 (https://openfontlicense.org), which allows bundling and
redistribution with software. Each family keeps its own copyright.

| Files | Family | Source |
| --- | --- | --- |
| `source-serif-4-*.woff2` | Source Serif 4 (Adobe) | the Claude Code in Telegram video's `hf/assets/fonts/` (Google Fonts, Latin subset) |
| `dm-sans-*.woff2` | DM Sans (Colophon / Google) | same |
| `caveat-*.woff2` | Caveat (Impallari Type) | same |
| `jetbrains-mono-latin-*.woff2` | JetBrains Mono (JetBrains) | fontsource `@fontsource/jetbrains-mono@5.3.0`, Latin subset |
| `noto-naskh-arabic-arabic-*.woff2` | Noto Naskh Arabic (Google) | fontsource `@fontsource/noto-naskh-arabic@5.3.0`, Arabic subset |
| `ibm-plex-sans-arabic-arabic-*.woff2` | IBM Plex Sans Arabic (IBM) | fontsource `@fontsource/ibm-plex-sans-arabic@5.3.0`, Arabic subset |

Arabic falls back inside each stack: the serif (titles, kinetic lines) to Noto Naskh Arabic, a book Naskh whose
contrast and 400/600/700 weights sit next to Source Serif 4; the sans (kickers, subs) to IBM Plex Sans Arabic.
