import { Marked, Renderer } from "marked";
const escape = (value: string) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
/** Render Markdown without executing raw HTML or loading external resources. */
export function renderMarkdown(source: string): string {
  const renderer = new Renderer();
  renderer.html = (token) => escape(token.text);
  renderer.image = (token) =>
    `<span>${escape(token.text || "Image")} (image not loaded)</span>`;
  renderer.link = function (token) {
    return this.parser.parseInline(token.tokens);
  };
  return new Marked({ renderer }).parse(source, { async: false });
}
