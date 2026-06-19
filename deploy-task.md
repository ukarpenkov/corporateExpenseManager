# Пункт 1

**Статус:** Не выполнено

---

## Обзор

Эта лабораторная работа является частью 5-дневного интенсивного курса программирования Vibe Coding Course от Google на платформе Kaggle.

### Что вы узнаете
- Как подготовить локальный проект Ambient Expense Agent для размещения в облаке
- Как создать необходимые дескрипторы развертывания и оболочки для производственной среды
- Как проводить пробные запуски и развертывать код непосредственно в Agent Runtime
- Как отслеживать трассировку выполнения вашего производственного агента с помощью Cloud Trace

### Что вам понадобится
- Активный проект в Google Cloud с включенной функцией выставления счетов
- Установлен и авторизован SDK gcloud
- Установлен менеджер пакетов UV
- Установлена среда разработки Google Antigravity IDE

### Предварительные требования
В этом практическом занятии предполагается, что вы хорошо знакомы со следующими темами:
- Навигация по системе осуществляется с помощью терминала
- Основные концепции разработки на Python
- Основные концепции Google Cloud

---

# Пункт 2

**Статус:** ✅ Выполнено

---

## Настройте свою среду Google Cloud

Перед развертыванием необходимо настроить проект Google Cloud и включить необходимые API.

> **Мгновенная антигравитация:**
>
> ```
> Help me set up my Google Cloud environment. Connect to my project
> `YOUR_PROJECT_ID` in the global region, authenticate, and enable the necessary
> generative platform APIs (aiplatform.googleapis.com, cloudtrace.googleapis.com,
> cloudbuild.googleapis.com, agentregistry.googleapis.com).
> ```

Когда Antigravity выполнит это приглашение, он предложит и запустит необходимые команды терминала gcloud для настройки вашего проекта и включения сервисов.

**Примечание:** Если это новый проект, gcloud может сначала предложить вам включить API использования сервиса.

---

# Пункт 3

**Статус:** ✅ Выполнено

---

## Настройка навыков CLI и ADK для агентов

Для эффективной сборки и развертывания агентов ADK в Antigravity необходим набор инструментов ADK.

> **Скопируйте и вставьте следующую подсказку в Antigravity:**
>
> ```
> Install the agents-cli toolchain and its ADK skills so you can help me build
> an ADK agent. Run "uvx google-agents-cli setup", then confirm with
> "agents-cli info" and tell me which skills are now available.
> ```

Когда Antigravity отправляет это приглашение, он запускает в терминале `uvx google-agents-cli setup` для установки CLI и сопутствующих навыков.

**Примечание для пользователей Antigravity:** Во время выполнения этого практического задания Antigravity может генерировать планы реализации или отображать всплывающие окна перед выполнением команд или написанием кода.

**Совет по использованию квоты:** Если во время тестирования или разработки у вас закончится квота, переключитесь в Antigravity на другую доступную модель.

---

# Пункт 4

**Статус:** ✅ Выполнено

---

## Создайте свой проект агента

После настройки облачной среды и установки навыков работы с командной строкой вы готовы сгенерировать локальный код для вашего агента.

**Примечание для пользователей Kaggle 5 дней AI Agents:** Если вы успешно завершили этот практический семинар, вы можете пропустить этот этап создания шаблона и перейти к следующему шагу.

> **Мгновенная антигравитация:**
>
> ```
> Use Agents CLI to build a local prototype for an ambient expense agent that
> streamlines employee expense reporting by instantly approving standard claims
> while flagging larger expenses for review. Ensure the graph workflow is
> compatible with ADK 2.0 and includes an `auto_approve` node that automatically
> approves expenses under $100, and a `review_agent` node that triggers a
> human-in-the-loop pause (`RequestInput`) for expenses of $100 or more.
> ```

---

# Пункт 5

**Статус:** ✅ Выполнено

---

## Подготовка к развертыванию в производственной среде

Agent Runtime — это полностью управляемый сервис Google Cloud, позволяющий развертывать, управлять и масштабировать агентов ИИ в производственной среде.

### Почему развертывание в среде выполнения агента?
При локальной сборке агентов с помощью Antigravity ваш агент запускается на локальном компьютере по localhost.

### Преимущества Agent Runtime
- **Управляемое выполнение с сохранением состояния** — встроенное управление сессиями и сохранение данных в долговременной памяти
- **Безопасная песочница** — безопасное выполнение динамических вызовов инструментов и сгенерированного агентом кода
- **Наблюдаемость в корпоративной среде** — готовая к использованию потоковая передача телеметрии непосредственно в Cloud Trace и Cloud Logging

> **Мгновенная антигравитация:**
>
> ```
> Scaffold the production deployment files for Agent Runtime.
> ```

Эта команда автоматически сгенерирует:
- `app/agent_runtime_app.py` — Оболочка сервиса, готовая к использованию в производственной среде
- `deployment_metadata.json` — Схема структуры, используемая средой выполнения агента для запуска ресурсов

---

# Пункт 6

**Статус:** ✅ Выполнено

---

## Упаковка и локальная проверка

Перед началом загрузки в облако заблокируйте свои пакеты и проведите локальный пробный запуск, чтобы выявить потенциальные конфликты зависимостей.

> **Мгновенная антигравитация:**
>
> ```
> Lock my python dependencies and run a dry-run deployment to check for any
> configuration or dependency issues.
> ```

Когда Antigravity выполнит эту команду, сначала запустится `uv lock` для создания детерминированного файла блокировки, затем будет выполнена `agents-cli deploy --dry-run` для проверки корректности конфигурации.

---

# Пункт 7

**Статус:** ✅ Выполнено

---

## Развертывание в среде выполнения агента

Разверните свой агент Ambient Expense в среде выполнения агентов.

> **Мгновенная антигравитация:**
>
> ```
> Deploy this agent to Agent Runtime.
> ```

Процесс упаковки, загрузки и подготовки среды выполнения агента обычно занимает **5–10 минут**.

**Полезный совет:** Если вы предпочитаете не блокировать терминал во время длительных развертываний, вы можете использовать флаг `--no-wait` для асинхронного запуска развертывания и проверить ход выполнения позже с помощью `agents-cli deploy --status`.

**Результат:** Развернут в Cloud Run (вместо Agent Runtime, т.к. Agent Runtime не поддерживает Pub/Sub триггеры).
- URL: `https://corporateexpensemanager-3sms5oeluq-uc.a.run.app`
- Регион: `us-central1`
- Статус: `Ready`

---

# Пункт 8

**Статус:** ✅ Выполнено

---

## Проверьте своего агента

После развертывания агента вы можете убедиться, что он автоматически одобряет небольшие расходы и корректно помечает их для проверки человеком при оформлении более крупных расходов.

> **Запросите у LLM подтверждение работы развернутого движка:**
>
> ```
> Test my deployed Agent Runtime engine with two test cases: first a standard
> meal expense of $50 to verify automatic approval, and second, a client dinner
> expense of $150 to verify that the human-in-the-loop pause is triggered.
> ```

### Тест автоматического одобрения

```json
{"data": {"amount": 50.0, "submitter": "user@example.com", "category": "meals", "description": "Lunch", "date": "2026-06-04"}}
```

### Тест сценария "человек в цикле" (HITL)

```json
{"data": {"amount": 150.0, "submitter": "user@example.com", "category": "meals", "description": "Client dinner", "date": "2026-06-04"}}
```

---

# Пункт 9

**Статус:** Не выполнено

---

## Контролируйте и наблюдайте за своим производственным агентом

С Agent Runtime телеметрия автоматически подключается. Каждое взаимодействие, вызов модели и выполнение инструмента передают в режиме реального времени журналы и данные в ваш проект.

- **Проверка трассировки** — Откройте консоль Cloud Trace, чтобы проверить карты транзакций в реальном времени
- **Журналы аудита** — Используйте Cloud Logging для анализа стандартного вывода в реальном времени
- **Сводная аналитика** — Выполните запрос к журналам в BigQuery с помощью SQL

### SQL-запрос для расчета коэффициентов одобрения

```sql
SELECT
  COUNTIF(REGEXP_CONTAINS(response_text, r'(?i)approved')) AS approved_count,
  COUNTIF(REGEXP_CONTAINS(response_text, r'(?i)rejected')) AS rejected_count,
  COUNT(1) AS total_processed,
  SAFE_DIVIDE(COUNTIF(REGEXP_CONTAINS(response_text, r'(?i)approved')), COUNT(1)) AS approval_ratio
FROM
  `[YOUR_PROJECT_ID].[YOUR_DATASET_ID].v_agent_response`
WHERE
  agent = 'expense_processor';
```

---
