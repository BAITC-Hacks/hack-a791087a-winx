# Сторонние компоненты и источники

| Компонент | Ссылка | Лицензия / условия | Зачем |
|---|---|---|---|
| Python 3.11+ | https://www.python.org/ | PSF License | Язык, venv, unittest, запуск |
| Streamlit 1.64.0 | https://github.com/streamlit/streamlit | Apache-2.0 | Локальный интерфейс и AppTest |
| OpenAI Python SDK 3.19.0 | https://github.com/openai/openai-python | Apache-2.0 | Responses API |
| python-dotenv 1.2.3 | https://github.com/theskumar/python-dotenv | BSD-3-Clause | Загрузка локального .env |
| OpenAI API, модель задаётся OPENAI_MODEL | https://openai.com/policies/services-agreement/ | Условия сервиса OpenAI; не open source | Необязательное объяснение готового результата |
| Официальная документация OpenAI | https://developers.openai.com/api/docs/libraries | Документация OpenAI; ссылка, без копирования больших фрагментов | Сигнатуры Responses API |
| ТЗ и синтетический датасет HackAlem AI | [TASK.md](docs/TASK.md), [DATASET.md](docs/DATASET.md) | Предоставлены организаторами; отдельная лицензия не указана | Районы, меры, формула и правила |

Транзитивные зависимости устанавливаются pip по метаданным перечисленных пакетов;
их список, версии и лицензии фиксируются после установки в `docs/DEPENDENCIES.json`.
Чужие шаблоны, изображения и фрагменты продуктового кода не использовались.

## Инструменты разработки

| Инструмент | Ссылка | Условия | Использование |
|---|---|---|---|
| Codex / OpenAI | https://openai.com/codex/ | Условия OpenAI | Планирование, код, документация и проверка |
| Субагент gpt-6-luna | https://openai.com/ | Условия OpenAI | Независимое чтение ТЗ, создание части скелета и аудит математики/AI/UI |
| Скилл subagent-models | Локальный `.codex/skills/subagent-models/SKILL.md` | Пользовательский скилл; лицензия не указана | Выбор модели и effort субагентов |
| Скилл OpenAI Docs | https://github.com/openai/skills | См. лицензию источника | Проверка документации SDK |
| Скилл openai-platform-api-key | Локальный плагин openai-developers, skills/openai-platform-api-key | См. лицензию плагина | Проверка наличия ключа без вывода значения; правила подключения существующего ключа |
| Документация OpenAI по ключам и расходам | https://developers.openai.com/api/docs/guides/production-best-practices ; https://developers.openai.com/api/docs/guides/spend-limits | Документация OpenAI | Безопасная серверная конфигурация и различие уведомлений/лимитов расходов |
| Скилл idea-forge | Локальный `.codex/skills/idea-forge/SKILL.md` | Пользовательский скилл; лицензия не указана | Генерация и уточнение концепции, собранной в docs/PROPOSAL.md |
| Скиллы Superpowers: using-superpowers, brainstorming, writing-plans, dispatching-parallel-agents, systematic-debugging, test-driven-development, requesting-code-review, verification-before-completion | https://github.com/obra/superpowers | См. лицензию источника | Уточнение идеи, технический план, аудит, безопасный launcher с проверкой границ ввода |
| Документация Streamlit Components v2 и Three.js | https://docs.streamlit.io/develop/concepts/custom-components/components-v2 ; https://threejs.org/manual/pages/installation.html | Документация источников; без заимствования продуктового шаблона | Проверка способа локального встраивания 3D при планировании; Three.js пока не установлен |
| Git | https://git-scm.com/ | GPL-2.0 | История и синхронизация команды |
| pip | https://github.com/pypa/pip | MIT | Установка зависимостей |

AGENTS.md первоначально скопирован из пользовательского `.codex/hackalem/AGENTS.md`;
позже добавлен приоритет нового указания пользователя об обязательном 3D без отсечения по сроку.
