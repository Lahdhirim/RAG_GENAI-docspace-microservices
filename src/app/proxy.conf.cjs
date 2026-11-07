// Keep the Angular page route and the existing API URL on the same origin.
module.exports = {
  "/documents": {
    target: "http://127.0.0.1:8000",
    secure: false,
    changeOrigin: true,
    bypass(request) {
      if (request.headers.accept?.includes("text/html")) return "/index.html";
      return undefined;
    },
  },
};
