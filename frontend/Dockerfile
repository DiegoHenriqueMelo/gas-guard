# ---------- etapa 1: compilar ----------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# ATENCAO: o Vite embute VITE_API_URL no bundle em tempo de BUILD, nao de
# execucao. E o NAVEGADOR quem chama a API, e ele roda na maquina do usuario,
# fora da rede do compose. Por isso o valor e "localhost:8000" (a porta
# publicada do backend) e NAO "backend:8000", que so existe dentro da rede.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ---------- etapa 2: servir ----------
# So o resultado do build vai para a imagem final: nada de node_modules.
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
