const env = process.env.ENV || "development";
const host = env === "production" ? "doc_manager_api" : "127.0.0.1";

console.log(`Connecting to API host: ${host}`);

module.exports = {
  "/documents": {
    target: `http://${host}:8000`,
    secure: false,
    changeOrigin: true,
    bypass(request) {
      if (request.headers.accept?.includes("text/html")) {
        return "/index.html";
      }
      return undefined;
    },
  },
};
