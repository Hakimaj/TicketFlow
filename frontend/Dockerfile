# TicketFlow web client — build the SPA, serve it with nginx.
#
#   docker build -t ticketflow-web ./frontend
#
# The production build defaults to a same-origin `/api/v1` base URL (see
# src/config/app-mode.ts), and nginx proxies `/api/` to the `api` service, so no
# build-time API location is required. VITE_DATA_MODE is never set here: demo
# fixtures stay opt-in only.

FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
