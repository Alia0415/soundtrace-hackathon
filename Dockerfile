FROM nginx:stable-alpine

ENV PORT=80
ENV NGINX_ENVSUBST_FILTER=PORT

COPY deploy/tencent-pages/ /usr/share/nginx/html/
COPY deploy/cloudbase-nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -q -O - "http://127.0.0.1:${PORT}/health" || exit 1
