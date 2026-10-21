# ---------- etapa 1: compilar ----------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Sem VITE_API_URL: o frontend chama /api e /ws na propria origem, e o nginx
# abaixo repassa para a API. Trocar o endereco da API nao exige rebuild.
RUN npm run build

# ---------- etapa 2: servir ----------
# So o resultado do build vai para a imagem final: nada de node_modules.
# A variante "unprivileged" roda o nginx sem root.
FROM nginxinc/nginx-unprivileged:1.31-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
