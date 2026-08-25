📦gas-guard
 ┣ 📂backend
 ┃ ┣ 📂alembic
 ┃ ┃ ┣ 📂versions
 ┃ ┃ ┃ ┗ 📜(versions)
 ┃ ┃ ┣ 📜env.py
 ┃ ┃ ┣ 📜README
 ┃ ┃ ┗ 📜script.py.mako
 ┃ ┣ 📂app
 ┃ ┃ ┣ 📂ambientes
 ┃ ┃ ┃ ┣ 📜__init__.py
 ┃ ┃ ┃ ┗ 📜models.py
 ┃ ┃ ┣ 📂core
 ┃ ┃ ┃ ┣ 📜__init__.py
 ┃ ┃ ┃ ┣ 📜database.py
 ┃ ┃ ┃ ┗ 📜influx.py
 ┃ ┃ ┣ 📂dispositivos
 ┃ ┃ ┃ ┣ 📜__init__.py
 ┃ ┃ ┃ ┣ 📜exceptions.py
 ┃ ┃ ┃ ┣ 📜models.py
 ┃ ┃ ┃ ┣ 📜repository.py
 ┃ ┃ ┃ ┣ 📜router.py
 ┃ ┃ ┃ ┣ 📜schemas.py
 ┃ ┃ ┃ ┗ 📜service.py
 ┃ ┃ ┣ 📂leituras
 ┃ ┃ ┣ 📂mqtt
 ┃ ┃ ┣ 📜__init__.py
 ┃ ┃ ┗ 📜main.py
 ┃ ┣ 📜alembic.ini
 ┃ ┣ 📜Dockerfile
 ┃ ┣ 📜requirements.txt
 ┃ ┗ 📜ruff.toml
 ┣ 📂frontend
 ┃ ┣ 📂public
 ┃ ┃ ┣ 📜favicon.svg
 ┃ ┃ ┗ 📜icons.svg
 ┃ ┣ 📂src
 ┃ ┃ ┣ 📂assets
 ┃ ┃ ┃ ┣ 📜hero.png
 ┃ ┃ ┃ ┣ 📜vite.svg
 ┃ ┃ ┃ ┗ 📜vue.svg
 ┃ ┃ ┣ 📂components
 ┃ ┃ ┃ ┗ 📜HelloWorld.vue
 ┃ ┃ ┣ 📜App.vue
 ┃ ┃ ┣ 📜main.ts
 ┃ ┃ ┗ 📜style.css
 ┃ ┣ 📜.gitignore
 ┃ ┣ 📜Dockerfile
 ┃ ┣ 📜index.html
 ┃ ┣ 📜package-lock.json
 ┃ ┣ 📜package.json
 ┃ ┣ 📜README.md
 ┃ ┣ 📜tsconfig.app.json
 ┃ ┣ 📜tsconfig.json
 ┃ ┣ 📜tsconfig.node.json
 ┃ ┗ 📜vite.config.ts
 ┣ 📂infra
 ┃ ┣ 📂mosquitto
 ┃ ┃ ┗ 📂config
 ┃ ┃ ┃ ┗ 📜mosquitto.conf
 ┃ ┗ 📂postgres
 ┣ 📜.env
 ┣ 📜.env.example
 ┣ 📜.gitignore
 ┣ 📜ARCHITECTURE.MD
 ┣ 📜docker-compose.yml
 ┗ 📜README.md
