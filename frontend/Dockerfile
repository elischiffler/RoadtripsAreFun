# syntax=docker/dockerfile:1
FROM node:24.21.0-alpine3.23@sha256:9ec4a2e289874ed0d722e1772ec2de45d2801541db8612f3638b26f128c69ac2 AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_BACKEND_SERVER
ARG VITE_LOCAL_JOURNEY=false
ARG VITE_USERPOOL_ID=us-west-1_fixture
ARG VITE_CLIENT_ID=localfixture
ARG VITE_COGNITO_ENDPOINT=http://127.0.0.1:8999
RUN test -n "$VITE_BACKEND_SERVER" && npm run build

FROM nginx:1.30.5-alpine3.24@sha256:bf3201ab56f23e5954646379c775d511fc466e9f11376d9725361064ad07ed35
ARG VCS_REF
RUN test -n "$VCS_REF" && rm -rf /usr/share/nginx/html && mkdir -p /usr/share/nginx/html
LABEL org.opencontainers.image.revision=$VCS_REF org.opencontainers.image.source="https://github.com/elischiffler/RoadtripsAreFun"
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
USER nginx
EXPOSE 8080
STOPSIGNAL SIGQUIT
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["nginx", "-g", "daemon off;"]
