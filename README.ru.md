# Strapi-Proj-Bot

**Strapi-Proj-Bot** — модульная платформа для сбора, агрегации и структурирования данных о проектах с поддержкой парсинга сайтов, X (Twitter), коллекционных сервисов типа linktr.ee и автоматической очистки данных. Позволяет централизованно управлять настройками, генерировать отчеты в различных форматах и масштабировать систему под любые задачи мониторинга, анализа и агрегации проектов.

## Основные возможности

* **Модульная архитектура** — плагины для сайтов, X-профилей, коллекционных сервисов.
* **Гибкая обработка ссылок** — парсинг из био, коллекционных страниц, генерация и автоматическая нормализация (очистка хвостов, единый формат для YouTube, docs, GitHub и др.).
* **Централизованная настройка** — все параметры и добавление новых проектов в одном `config.json`.
* **Мультиязычность** — легко добавлять новые языки интерфейса.
* **Полная автоматизация** — запуск одной командой, без ручного вмешательства.
* **Обход защит сайтов** — автоматический переход на браузерный режим при Cloudflare, JS-challenge, антиботах.
* **Асинхронная и быстрая обработка** — все этапы пайплайна работают параллельно.
* **Кэширование данных** — минимизация повторных запросов, ускорение парсинга.
* **Логирование** — подробный лог всех шагов для отладки и аудита.

## Где можно использовать

* **Агрегация и мониторинг крипто- и IT-проектов**
* **Автоматизация сбора контактных данных**
* **Обновление витрин и агрегаторов проектов**
* **Парсинг публичных профилей и документации**

## Технологический стек

* **Python** — основной язык разработки
* **Requests, BeautifulSoup** — парсинг и обработка сайтов
* **Playwright** — парсинг X-профилей (через fingerprint)

### Поддерживаемые источники

| Источник          | Описание                                  |
|-------------------|-------------------------------------------|
| `website`         | Главный сайт проекта                      |
| `docs`            | Документация, whitepaper                  |
| `X/Twitter`       | Bio и линки профиля, аватар               |
| `linktr.ee`/etc.  | Сбор всех связанных соцсетей              |
| `YouTube`         | Корректная агрегация только каналов       |
| `GitHub`          | Поддержка фильтрации только по org/user   |

## Архитектура

### Компоненты системы

1. **Парсеры (`core/*.py`)** — обертки над разными источниками (сайты, коллекционные сервисы, X/Twitter).
2. **Центральная точка входа (`config/start.py`)** — управляет пайплайном сбора, нормализации и сохранения данных.
3. **Шаблоны (`templates/`)** — структуруют результат под формат системы.
4. **Логирование (`logs/`)** — ведет полный журнал работы.
5. **Конфигурация (`config/config.json`)** — все цели, настройки и параметры.

### Структура проекта

```
strapi-proj-bot/
├── config/
│   ├── apps/
│   │   └── {project}.json         # Конфиг отдельного приложения
│   ├── config.json                # Центральная конфигурация (все проекты, параметры)
│   └── start.py                   # Главный скрипт пайплайна (точка входа)
├── core/
│   ├── api_ai.py                  # Интеграция с AI
│   ├── api_strapi.py              # Интеграция с API Strapi
│   ├── browser_fetch.js           # Парсер сайтов через браузер
│   ├── install.py                 # Скрипт автоустановки зависимостей
│   ├── log_utils.py               # Логирование
│   ├── orchestrator.py            # Оркестрация (main async pipeline)
│   ├── package.json               # Зависимости парсеров (Node)
│   ├── package-lock.json          # Лок-файл зависимостей
│   ├── twitter_parser.js          # Парсер X профилей (Node)
│   └── web_parser.py              # Модуль парсинга ссылок
├── logs/
│   ├── ai.log                     # Лог AI
│   ├── host.log                   # Хостовой лог пайплайна
│   ├── setup.log                  # Лог установки зависимостей
│   └── strapi.log                 # Лог отправки в Strapi
├── storage/
│   └── apps/
│       └── {project}/
│           └── main.json          # Результаты парсинга по проекту
├── templates/
│   └── main_template.json         # Шаблон структуры main.json
├── requirements.txt               # Python зависимости
├── README.md                      # Документация
└── start.sh                       # Bash-скрипт быстрого запуска пайплайна
```

## Pipeline: Как это работает?

1. **Запуск системы**:
   * `start.sh` → `config/start.py` → `core/orchestrator.py`
2. **Автоустановка зависимостей**:
   * `config/start.py` →`core/install.py`:
      * Установка Python-пакетов.
      * Node.js-модули для парсинга и обхода антибот-защиты.
      * Playwright подготавливает браузеры для headless-парсинга.
3. **Загрузка конфигурации и шаблонов**:
   * Загружается основной конфиг (список проектов и настроек).
   * Подтягивается шаблон данных для `main.json` (структура и ключи).
4. **Асинхронный парсинг и сбор данных для каждой цели**:
   * **Основной парсинг**: Осуществляется через `requests` + `BeautifulSoup` (быстро и эффективно для большинства сайтов).
   * **Обход защиты (Cloudflare, JS, антибот):** Если сайт защищен или требуется рендеринг JS, пайплайн автоматически переключается на `Playwright` + `Fingerprint Suite` (`core/browser_fetch.js`).
   * **Парсинг Twitter/X**: Всегда идет через отдельный браузерный парсер (`core/twitter_parser.js`), эмулирующий реальное поведение пользователя.
   * **Обработка коллекционных и внутренних ссылок**: Внутренние страницы, docs, linktr.ee, read.cv и др. обрабатываются по той же схеме: сначала `requests`, при необходимости через `Playwright`.
   * **Детектируются и нормализуются все социальные ссылки и docs**: GitHub, Discord, Telegram, Medium, YouTube, LinkedIn, Reddit, официальный сайт, техническая документация.
   * **Кэширование HTML (in-memory)**: Для ускорения повторных запусков и снижения нагрузки на сайты.
   * **Асинхронность и параллелизм**: Все процессы по каждому проекту (AI-генерация, поиск CoinGecko, web-парсинг) выполняются параллельно, что ускоряет сбор.
   * **Ретраи и обработка ошибок**: Ключевые блоки обернуты в `try/except`, используются автоматические ретраи при неудачных запросах, ошибки логируются.
5. **Генерация описаний и enrichment**:
   * Автоматический запуск AI-генерации кратких и полных описаний проекта.
   * Поиск информации о токене/коине через CoinGecko API.
   * Фоллбеки на ручной шаблон при отсутствии данных.
6. **Сохранение результата**:
   * Все данные по каждому проекту сохраняются в `storage/total/{project}/main.json`.
6. **Публикация и интеграция**:
   * Готовые `main.json` автоматически заливаются в Strapi через API.
   * Файлы (аватарки, лого) также автоматически прикрепляются в Strapi.

**Запускать нужно только `start.sh` — все остальное сделает бот!**

## Установка и запуск

```bash
git clone https://github.com/beesyst/strapi-proj-bot.git
cd strapi-proj-bot
bash start.sh
```

## Настройка конфигурации
Все параметры задаются в файле config/config.json:

| Параметр   | Значение по умолчанию | Описание                                                     |
|------------|-----------------------|--------------------------------------------------------------|
| `apps`     | `[ "babylon" ]`       | Список целей (объекты-проекты с настройками и enabled)       |
| `enabled`  | `true`                | Флаг: включен ли проект (false — будет полностью проигнорирован) |
| `link_collections` | `[ "linktr.ee" ]` | Массив сервисов для глубокого парсинга                 |

## Терминал и статусы

В процессе работы бот выводит для каждого проекта только итоговый статус:

* `[add]` — проект добавлен впервые (создан новый main.json, отправлен в Strapi)
* `[update]` — данные проекта обновлены (main.json перезаписан, отправлен в Strapi)
* `[skip]` — данные не изменились (ничего не отправлялось)
* `[error]` — возникла ошибка при сборе или отправке

