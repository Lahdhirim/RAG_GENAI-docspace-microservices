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
      // /documents is both an Angular route and an API endpoint; browser
      // navigation needs the app shell while JSON requests go to the API.
      if (request.headers.accept?.includes("text/html")) return "/index.html";
      return undefined;
    },
  },
  "/documents/*/preview": apiProxy,
  "/parsing_statuses": apiProxy,
};
