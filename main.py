import requests
import json
import time
import hashlib
import os
from flask import Flask, Response, request
from typing import Generator, List, Dict, Optional
from datetime import datetime

# 智谱官方 SDK
from zai import ZhipuAiClient

# ===================== 初始化 =====================
app = Flask(__name__)

# 【请替换为你的实际配置】

# API位于 /{SUMMARY_KEY}/summary/{page_name}

CONFIG = {
    "ZHIPU_API_KEY": "",
    "WIKI_API_KEY": "",
    "GRAPHQL_URL": "http://localhost:2525/graphql",
    "SUMMARY_KEY": "",
    "ZHIPU_MODEL": "GLM-4.7",
    "ZHIPU_TEMPERATURE": 0.3,
    "ZHIPU_MAX_TOKENS": 3000,  # 增加到3000以支持更详细的总结
}

# 初始化客户端
client = ZhipuAiClient(api_key=CONFIG["ZHIPU_API_KEY"])

# ===================== Wiki 页面操作 =====================
def get_wiki_page_info(page_name: str) -> Dict:
    """获取页面基础信息（ID、标题、更新时间）"""
    try:
        query = """
        {
          pages {
            list {
              id
              title
              path
              updatedAt
              isPublished
            }
          }
        }
        """
        headers = {"Authorization": f"Bearer {CONFIG['WIKI_API_KEY']}"}
        r = requests.post(
            CONFIG["GRAPHQL_URL"],
            json={"query": query},
            headers=headers,
            timeout=10
        )
        
        if r.status_code != 200:
            raise Exception(f"Wiki请求失败，状态码：{r.status_code}")
        
        r_json = r.json()
        if "errors" in r_json:
            raise Exception(f"Wiki GraphQL错误：{json.dumps(r_json['errors'], ensure_ascii=False)}")

        pages = r_json["data"]["pages"]["list"]
        target_page = None
        
        # 宽松匹配：标题包含 / 路径包含（不区分大小写）
        page_name_lower = page_name.lower()
        for p in pages:
            if not p.get("isPublished"):
                continue
                
            title_lower = p["title"].lower()
            path_lower = p["path"].lower()
            
            if title_lower == page_name_lower:
                target_page = p
                break
            elif page_name_lower in title_lower:
                target_page = p
            elif page_name_lower in path_lower and not target_page:
                target_page = p

        if not target_page:
            available_titles = [p["title"] for p in pages if p.get("isPublished")]
            raise Exception(f"未找到匹配的页面！可用页面：{available_titles}")

        return {
            "page_id": str(target_page["id"]),
            "title": target_page["title"],
            "updated_at": target_page["updatedAt"],
            "path": target_page["path"]
        }
        
    except Exception as e:
        raise Exception(f"获取Wiki页面信息失败：{str(e)}")

def get_wiki_content(page_name: str) -> Dict:
    """获取页面完整内容和更新信息"""
    try:
        # 获取页面基础信息
        page_info = get_wiki_page_info(page_name)
        page_id = page_info["page_id"]

        # 获取页面详情
        query_single = f"""
        {{ 
          pages {{ 
            single(id: {page_id}) {{ 
              content 
              title 
              updatedAt 
              isPublished 
            }} 
          }} 
        }}
        """
        
        headers = {"Authorization": f"Bearer {CONFIG['WIKI_API_KEY']}"}
        r2 = requests.post(
            CONFIG["GRAPHQL_URL"],
            json={"query": query_single},
            headers=headers,
            timeout=10
        ).json()

        if "errors" in r2:
            raise Exception(f"获取页面详情错误：{json.dumps(r2['errors'], ensure_ascii=False)}")

        page_data = r2["data"]["pages"]["single"]
        if not page_data:
            raise Exception(f"页面ID {page_id} 不存在详情")

        return {
            "content": page_data.get("content", ""),
            "title": page_data.get("title", ""),
            "updated_at": page_data.get("updatedAt", page_info["updated_at"]),
            "page_id": page_info["page_id"],
            "path": page_info["path"]
        }
        
    except Exception as e:
        raise Exception(f"获取Wiki内容失败：{str(e)}")
        
        
def update_page_description(
    page_id: int,
    new_description: str
) -> dict:
    # 第一步：获取页面的现有内容（只查询确定可用的字段）
    print("正在获取页面现有内容...")
    page_info = get_page_info(page_id, silent=True)
    
    if "error" in page_info or "errors" in page_info:
        print("✗ 无法获取页面信息")
        return page_info
    
    page_data = page_info.get("data", {}).get("pages", {}).get("single")
    if not page_data:
        return {"error": "页面不存在"}

    print(f"✓ 已获取页面内容")
    
    # GraphQL endpoint
    graphql_endpoint = CONFIG["GRAPHQL_URL"]
    
    mutation = """
    mutation UpdatePage(  
        $id: Int!,  
        $content: String!,  
        $description: String!,  
        $title: String!,  
        $path: String!,  
        $editor: String!,  
        $isPublished: Boolean!,  
        $isPrivate: Boolean!,  
        $scriptCss: String!,    
        $scriptJs: String!,  
        $locale: String!,  
        $tags: [String]!,  
        $publishStartDate: Date,  
        $publishEndDate: Date  
    ) {  
        pages {  
            update(  
                id: $id  
                content: $content  
                description: $description  
                title: $title  
                path: $path  
                editor: $editor  
                isPublished: $isPublished  
                isPrivate: $isPrivate  
                scriptCss: $scriptCss  
                scriptJs: $scriptJs  
                locale: $locale  
                tags: $tags  
                publishStartDate: $publishStartDate  
                publishEndDate: $publishEndDate  
            ) {  
                responseResult {  
                    succeeded  
                    errorCode  
                    slug  
                    message  
                }  
                page {  
                    id  
                    path  
                    title  
                    description  
                    updatedAt  
                }  
            }  
        }  
    }
    """
    
    # 准备变量 - 使用合理的默认值
    # 这些默认值基于 GitHub Discussion #6314 中的示例
    variables = {  
        "id": page_data.get("id"),  
        "content": page_data.get("content", ""),  
        "description": new_description,  
        "title": page_data.get("title", ""),  
        "path": page_data.get("path", ""),  
        "editor": page_data.get("editor", "markdown"),  
        "isPublished": page_data.get("isPublished", True),  
        "isPrivate": page_data.get("isPrivate", False),  
        "locale": page_data.get("locale", "zh"),  
        "tags": [tag["tag"] for tag in page_data.get("tags", [])],  
        "scriptCss": page_data.get("scriptCss", ""),  
        "scriptJs": page_data.get("scriptJs", ""),  
        "publishStartDate": page_data.get("publishStartDate", ""),  
        "publishEndDate": page_data.get("publishEndDate", "")  
    }
    
    # 准备请求头
    headers = {
        "Authorization": f"Bearer {CONFIG['WIKI_API_KEY']}",
        "Content-Type": "application/json"
    }
    
    # 准备请求体
    payload = {
        "query": mutation,
        "variables": variables
    }
    
    try:
        # 发送请求
        print("正在更新页面描述...")
        response = requests.post(
            graphql_endpoint,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        # 检查 HTTP 状态码
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 检查 GraphQL 错误
        if "errors" in result:
            print("GraphQL 错误:")
            for error in result["errors"]:
                print(f"  - {error.get('message', 'Unknown error')}")
            return result
        
        # 检查操作是否成功
        if result.get("data", {}).get("pages", {}).get("update"):
            update_result = result["data"]["pages"]["update"]
            response_result = update_result.get("responseResult", {})
            
            if response_result.get("succeeded"):
                print("✓ 页面简短说明更新成功!")
                page_info = update_result.get("page", {})
                print(f"  页面 ID: {page_info.get('id')}")
                print(f"  页面路径: {page_info.get('path')}")
                print(f"  页面标题: {page_info.get('title')}")
                print(f"  新的说明: {page_info.get('description')}")
                print(f"  更新时间: {page_info.get('updatedAt')}")
            else:
                print("✗ 更新失败:")
                print(f"  错误代码: {response_result.get('errorCode')}")
                print(f"  错误信息: {response_result.get('message')}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"请求错误: {e}")
        return {"error": str(e)}


def get_page_info(page_id: int, silent: bool = False) -> dict:
    """
    获取页面信息（只查询基本字段）
    
    参数:
        wikijs_url: Wiki.js 实例的 URL
        api_token: API 访问令牌
        page_id: 页面 ID
        silent: 是否静默模式（不打印信息）
    
    返回:
        dict: 页面信息
    """
    
    graphql_endpoint = CONFIG["GRAPHQL_URL"]
    
    # 只查询最基本且确定可用的字段
    query = """
    query GetPage($id: Int!) {  
        pages {  
            single(id: $id) {  
                id
                path
                title  
                description  
                isPrivate  
                isPublished  
                publishStartDate  
                publishEndDate  
                tags {  
                    tag  
                    title  
                }  
                content   
                createdAt  
                updatedAt  
                editor  
                locale  
                scriptCss  
                scriptJs  
            }  
        }  
    }
    """
    
    variables = {"id": page_id}
    
    headers = {
        "Authorization": f"Bearer {CONFIG['WIKI_API_KEY']}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": query,
        "variables": variables
    }
    
    try:
        response = requests.post(
            graphql_endpoint,
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            if not silent:
                print("GraphQL 错误:")
                for error in result["errors"]:
                    print(f"  - {error.get('message')}")
            return result
        
        page = result.get("data", {}).get("pages", {}).get("single")
        return result
        
    except requests.exceptions.RequestException as e:
        if not silent:
            print(f"请求错误: {e}")
        return {"error": str(e)}

# ===================== 核心总结函数（含缓存逻辑） =====================
PROCESSED_PAGES = set()

def generate_summary_stream(page_name: str) -> Generator[str, None, None]:
    """生成流式总结，并自动更新页面描述"""
    global PROCESSED_PAGES
    
    if page_name == "home":
        yield f"data: 主页不能生成总结"
        yield f"data: [DONE]\n\n"
        return
    
    if page_name in PROCESSED_PAGES:
        yield f"data: 页面「{page_name}」已处理，跳过生成\n\n"
        PROCESSED_PAGES.remove(page_name)  # 移出集合，下一次可以重新触发
        yield f"data: [DONE]\n\n"
        return

    try:
        # 1. 获取页面基础信息（含更新时间）
        page_data = get_wiki_content(page_name)
        page_id = page_data["page_id"]
        page_content = page_data["content"]
        page_title = page_data["title"]
        page_updated_at = page_data["updated_at"]

        if not page_content or page_content.strip() == "":
            yield f"data: ❌ 页面「{page_title}」内容为空\n\n"
            yield f"data: [DONE]\n\n"
            return

        # 3. 缓存未命中/页面已更新，调用AI生成新总结
        yield "\n\n"
        time.sleep(0.3)

        system_content = """"你是专业的信息压缩助手。你的任务是对文章进行高度概括性总结，而不是复述步骤。\
请遵守以下规则：\
1. 不得按步骤列出操作流程。\
2. 不得逐条改写原文内容。\
3. 只提炼核心目的、关键前提和主要过程。\
4. 字数控制在50字以内。\
5. 使用自然段换行，不得使用Markdown语法。"
"""
        # 调用智谱AI生成总结
        response = client.chat.completions.create(
            model=CONFIG["ZHIPU_MODEL"],
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"请对以下Wiki页面做高度概括性总结，而不是复述操作步骤：\n标题：{page_title}\n内容：{page_content}"}
            ],
            stream=True,
            temperature=CONFIG["ZHIPU_TEMPERATURE"],
            max_tokens=CONFIG["ZHIPU_MAX_TOKENS"],
        )

        summary_text = ""
        for chunk in response:
            if chunk.choices and hasattr(chunk.choices[0].delta, 'content'):
                delta_content = chunk.choices[0].delta.content
                if delta_content:
                    summary_text += delta_content
                    yield f"data: {delta_content}\n\n"

        if not summary_text:
            yield f"data: ❌ 「{page_title}」总结生成失败（内容为空）\n\n"

        # ===================== 自动更新页面描述 =====================
        update_result = update_page_description(
            page_id=int(page_id),
            new_description=summary_text.strip()
        )
        yield f"data: ✅ 页面描述已更新\n\n"
        
        yield f"data: [DONE]\n\n"
        PROCESSED_PAGES.add(page_name)
        
    except Exception as e:
        error_msg = f"❌ 处理失败：{str(e)}"
        yield f"data: {error_msg}\n\n"
        yield f"data: [ERROR]\n\n"


# ===================== 路由配置 =====================
@app.route(f'/{CONFIG["SUMMARY_KEY"]}/summary/<path:page_name>')
def get_wiki_summary(page_name):
    """Wiki页面摘要接口（带更新时间缓存）"""
    return Response(
        generate_summary_stream(page_name),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=4050, debug=False, threaded=True, use_reloader=False)