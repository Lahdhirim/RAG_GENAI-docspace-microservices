const env = process.env.ENV || "development";
const host = env === "production" ? "doc_manager_api" : "127.0.0.1";

console.log(`Connecting to API host: ${host}`);

const apiProxy = {
  target: `http://${host}:8000`,
  secure: false,
  changeOrigin: true,
};
module.exports = {
  "/documents": {
    ...apiProxy,
    bypass(request) {
      if (request.headers.accept?.includes("text/html")) return "/index.html";
      return undefined;
    },
  },
  "/documents/*/preview": apiProxy,
  "/parsing_statuses": apiProxy,
};
