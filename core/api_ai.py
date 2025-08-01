import asyncio
import json
import os

import requests
from core.log_utils import get_logger
from core.normalize import normalize_content_to_template_md

# Константы
PROMPT_TYPE_REVIEW_FULL = "review_full"
PROMPT_TYPE_CONNECTION = "connection"
PROMPT_TYPE_FINALIZE = "finalize"
PROMPT_TYPE_SHORT_DESCRIPTION = "short_description"
PROMPT_TYPE_PROJECT_CATEGORIES = "project_categories"
PROMPT_TYPE_SEO_SHORT = "seo_short"
PROMPT_TYPE_SEO_KEYWORDS = "seo_keywords"

# Логгер
logger = get_logger("ai")


# Загрузка OpenAI-конфига
def load_openai_config(config_path="config/config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["openai"]


# Загрузка промптов из файла
def load_prompts(prompt_path="config/prompt.json"):
    with open(prompt_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Рендер шаблона промпта с контекстом
def render_prompt(template, context):
    return template.format(**context)


# Универсальный вызов OpenAI API с полным конфигом
def call_ai_with_config(
    prompt, openai_cfg, custom_system_prompt=None, prompt_type="prompt"
):
    return call_openai_api(
        prompt,
        openai_cfg["api_key"],
        openai_cfg["api_url"],
        openai_cfg["model"],
        custom_system_prompt if custom_system_prompt else openai_cfg["system_prompt"],
        openai_cfg["temperature"],
        openai_cfg["max_tokens"],
        prompt_type=prompt_type,
    )


# Прямой вызов OpenAI API и логирование результата
def call_openai_api(
    prompt,
    api_key,
    api_url,
    model,
    system_prompt,
    temperature,
    max_tokens,
    prompt_type="prompt",
):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
        logger.info(f"[request] {prompt_type} prompt: %s...", prompt[:150])
        if resp.status_code == 200:
            result = resp.json()
            text = result["choices"][0]["message"]["content"]
            logger.info(f"[response] {prompt_type}: %s...", text[:150])
            return text
        else:
            logger.error(
                "[error] status: %s, response: %s", resp.status_code, resp.text[:500]
            )
    except Exception as e:
        logger.error("[EXCEPTION] %s", str(e))
    return ""


# Обновление contentMarkdown в main.json
def enrich_main_json(json_path, content):
    if not os.path.exists(json_path):
        logger.error("[ERROR] main.json not found: %s", json_path)
        return False
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["contentMarkdown"] = content
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("[OK] contentMarkdown обновлён для %s", json_path)
    return True


# Обновление shortDescription в main.json
def enrich_short_description(json_path, short_desc):
    if not os.path.exists(json_path):
        logger.error("[ERROR] main.json не найден: %s", json_path)
        return False
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["shortDescription"] = short_desc.strip()
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("[OK] shortDescription обновлён для %s", json_path)
    return True


# Асинх генерация описания для проекта (short_desc)
async def ai_generate_short_desc(data, prompts, openai_cfg, executor):
    def sync_ai_short():
        short_ctx = {
            "name2": data.get("name", ""),
            "website2": data.get("socialLinks", {}).get("websiteURL", ""),
        }
        short_prompt = render_prompt(prompts["short_description"], short_ctx)
        return call_ai_with_config(
            short_prompt, openai_cfg, prompt_type=PROMPT_TYPE_SHORT_DESCRIPTION
        )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_ai_short)


def load_allowed_categories(config_path="config/config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("categories", [])


# Нормализация и валидация категории из AI
def clean_categories(raw_cats, allowed_categories):
    if not isinstance(raw_cats, list):
        raw_cats = [c.strip() for c in raw_cats.split(",") if c.strip()]
    allowed = {c.lower(): c for c in allowed_categories}
    result = []
    for c in raw_cats:
        key = c.strip().lower()
        if key in allowed and allowed[key] not in result:
            result.append(allowed[key])
    return result[:3]


# Асинх генерация массива категорий для проекта
async def ai_generate_project_categories(
    data, prompts, openai_cfg, executor, allowed_categories=None
):
    def sync_ai_categories():
        context = {
            "name1": data.get("name", ""),
            "website1": data.get("socialLinks", {}).get("websiteURL", ""),
        }
        prompt = render_prompt(prompts["project_categories"], context)
        raw = call_ai_with_config(
            prompt, openai_cfg, prompt_type=PROMPT_TYPE_PROJECT_CATEGORIES
        )
        if not raw:
            return []
        if "," in raw:
            cats = [c.strip() for c in raw.split(",") if c.strip()]
        else:
            cats = [c.strip("-•. \t") for c in raw.splitlines() if c.strip()]
        if allowed_categories is not None:
            return clean_categories(cats, allowed_categories)
        return cats[:3]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_ai_categories)


def load_content_template(template_path="templates/content_template.json"):
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Асинх генерация полного markdown-контент проекта
async def ai_generate_content_markdown(
    data, app_name, domain, prompts, openai_cfg, executor
):
    def sync_ai_content():
        # Генерация "сырого" контента (review_full)
        context1 = {
            "name": data.get("name", domain),
            "website": data.get("socialLinks", {}).get("websiteURL", ""),
        }
        prompt1 = render_prompt(prompts["review_full"], context1)
        content1 = call_ai_with_config(
            prompt1, openai_cfg, prompt_type=PROMPT_TYPE_REVIEW_FULL
        )

        # Связь между проектами (connection)
        main_app_config_path = os.path.join("config", "apps", f"{app_name}.json")
        if os.path.exists(main_app_config_path):
            with open(main_app_config_path, "r", encoding="utf-8") as f:
                main_app_cfg = json.load(f)
            main_name = main_app_cfg.get("name", app_name.capitalize())
            main_url = main_app_cfg.get("url", "")
        else:
            main_name = app_name.capitalize()
            main_url = ""

        content2 = ""
        if domain.lower() != main_name.lower():
            context2 = {
                "name1": main_name,
                "website1": main_url,
                "name2": context1["name"],
                "website2": context1["website"],
            }
            prompt2 = render_prompt(prompts["connection"], context2)
            content2 = call_ai_with_config(
                prompt2, openai_cfg, prompt_type=PROMPT_TYPE_CONNECTION
            )

        all_content = content1
        if content2:
            all_content = (
                f"{content1}\n\n## {main_name} x {context1['name']}\n\n{content2}"
            )

        # Отдельный запрос на finalize
        context3 = {"connection_with": main_name if content2 else ""}
        finalize_instruction = render_prompt(prompts["finalize"], context3)

        # Вызов с кастомным system prompt = finalize_instruction
        final_content = call_ai_with_config(
            all_content,
            openai_cfg,
            custom_system_prompt=finalize_instruction,
            prompt_type=PROMPT_TYPE_FINALIZE,
        )

        from core.api_ai import load_content_template

        content_template = load_content_template()
        connection_title = f"{main_name} x {context1['name']}" if content2 else ""
        normalized_md = normalize_content_to_template_md(
            final_content, content_template, connection_title
        )
        return normalized_md.strip()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_ai_content)


# Асинх генерация SEO-описания
async def ai_generate_seo_desc(short_desc, prompts, openai_cfg, executor, max_len=50):
    def sync_seo_desc():
        context = {"short_desc": short_desc, "max_len": max_len}
        prompt = render_prompt(prompts["seo_short"], context)
        return call_ai_with_config(
            prompt, openai_cfg, prompt_type=PROMPT_TYPE_SEO_SHORT
        )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_seo_desc)


# Асинх генерация SEO-ключевых слов
async def ai_generate_keywords(content, prompts, openai_cfg, executor):
    def sync_keywords():
        context = {"content": content or ""}
        prompt = render_prompt(prompts["seo_keywords"], context)
        return call_ai_with_config(
            prompt, openai_cfg, prompt_type=PROMPT_TYPE_SEO_KEYWORDS
        )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_keywords)


# Асинхронная генерация seo_short с ретраями
async def ai_generate_seo_desc_with_retries(
    short_desc, prompts, openai_cfg, executor, max_len=50, max_retries=3
):
    desc = await ai_generate_seo_desc(
        short_desc, prompts, openai_cfg, executor, max_len=max_len
    )
    desc = (desc or "").strip()
    if len(desc) <= max_len:
        logger.info("[seo_desc_first_try] %s", desc)
        return desc

    base_prompt = prompts["seo_short"].format(short_desc=short_desc, max_len=max_len)
    for i in range(max_retries):
        retry_prompt = prompts["seo_short_retry"].format(
            base_prompt=base_prompt, max_len=max_len, result=desc
        )
        logger.info(
            f"[request] {PROMPT_TYPE_SEO_SHORT} prompt (retry #{i+1}): %s...",
            retry_prompt[:200],
        )
        desc_retry = await ai_generate_seo_desc(
            retry_prompt, prompts, openai_cfg, executor, max_len=max_len
        )
        desc_retry = (desc_retry or "").strip()
        logger.info("[seo_desc_retry #%d] %s (orig: %s)", i + 1, desc_retry, desc)
        if len(desc_retry) <= max_len:
            return desc_retry
        desc = desc_retry
    logger.warning("[seo_desc_truncated] %s", desc[:max_len])
    return desc[:max_len]


# Синхр генерация для оффлайн-режима
def process_all_projects():
    openai_cfg = load_openai_config()
    prompts = load_prompts()
    base_dir = os.path.join("storage", "apps")

    for app_name in os.listdir(base_dir):
        app_path = os.path.join(base_dir, app_name)
        if not os.path.isdir(app_path):
            continue

        for domain in os.listdir(app_path):
            partner_path = os.path.join(app_path, domain)
            if not os.path.isdir(partner_path):
                continue

            json_path = os.path.join(partner_path, "main.json")
            if not os.path.exists(json_path):
                continue

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("contentMarkdown"):
                logger.info("[SKIP] %s/%s: contentMarkdown уже есть", app_name, domain)
                continue

            # shortDescription
            if not data.get("shortDescription"):
                short_ctx = {
                    "name2": data.get("name", domain),
                    "website2": data.get("socialLinks", {}).get("websiteURL", ""),
                }
                short_prompt = render_prompt(prompts["short_description"], short_ctx)
                short_desc = call_ai_with_config(
                    short_prompt, openai_cfg, prompt_type=PROMPT_TYPE_SHORT_DESCRIPTION
                )
                if short_desc:
                    enrich_short_description(json_path, short_desc)
                else:
                    logger.error(
                        "[fail] Не удалось сгенерировать shortDescription для %s/%s",
                        app_name,
                        domain,
                    )

            # Основной markdown-обзор
            context1 = {
                "name": data.get("name", domain),
                "website": data.get("socialLinks", {}).get("websiteURL", ""),
            }
            prompt1 = render_prompt(prompts["review_full"], context1)
            content1 = call_ai_with_config(
                prompt1, openai_cfg, prompt_type=PROMPT_TYPE_REVIEW_FULL
            )

            # Связь с главным проектом (например, Celestia x Astria)
            main_app_config_path = os.path.join("config", "apps", f"{app_name}.json")
            if os.path.exists(main_app_config_path):
                with open(main_app_config_path, "r", encoding="utf-8") as f:
                    main_app_cfg = json.load(f)
                main_name = main_app_cfg.get("name", app_name.capitalize())
                main_url = main_app_cfg.get("url", "")
            else:
                main_name = app_name.capitalize()
                main_url = ""

            content2 = ""
            # Добавление связки, если имя не совпадает с основным проектом
            if domain.lower() != main_name.lower():
                context2 = {
                    "name1": main_name,
                    "website1": main_url,
                    "name2": context1["name"],
                    "website2": context1["website"],
                }
                prompt2 = render_prompt(prompts["connection"], context2)
                content2 = call_ai_with_config(
                    prompt2, openai_cfg, prompt_type=PROMPT_TYPE_CONNECTION
                )

            # Финализация и перевод
            all_content = content1
            if content2:
                all_content = (
                    f"{content1}\n\n## {main_name} x {context1['name']}\n\n{content2}"
                )
            context3 = {"connection_with": main_name if content2 else ""}
            prompt3 = render_prompt(prompts["finalize"], context3)
            final_content = call_ai_with_config(
                f"{all_content}\n\n{prompt3}",
                openai_cfg,
                prompt_type=PROMPT_TYPE_FINALIZE,
            )

            if final_content:
                enrich_main_json(json_path, final_content)
            else:
                logger.error(
                    "[fail] Не удалось сгенерировать финальный контент для %s/%s",
                    app_name,
                    domain,
                )


if __name__ == "__main__":
    process_all_projects()
