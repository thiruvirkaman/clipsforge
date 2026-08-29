# frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# No VITE_API_URL build arg needed: the app calls the API via a relative
# `/api/v1` path, proxied by nginx (see nginx.conf) to the backend service
# at container runtime -- same-origin, so no build-time URL and no CORS.
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
