// The three legal drafts live in src/legal and are bundled as raw text (see src/legal/README.md).
import terms from '../legal/terms.md?raw';
import privacy from '../legal/privacy.md?raw';
import contentPolicy from '../legal/content_policy.md?raw';

export const LEGAL_SOURCES: Record<string, string> = { terms, privacy, content_policy: contentPolicy };
