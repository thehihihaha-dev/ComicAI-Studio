import { redirect } from "next/navigation";

/**
 * ComicAI Studio Web Editor Canonical Redirect.
 *
 * Day 18 Phase 2 Workspace Unification:
 * The interactive CapCut-style 3-column Web Editor has been promoted to the canonical
 * project route at `/projects/[id]`. Accessing `/editor` automatically redirects
 * to the default benchmark project workspace.
 */
export default function ComicWebEditorRedirectPage() {
  redirect("/projects/92961605-5553-4df1-b74e-9a3bed5e14f5");
}
