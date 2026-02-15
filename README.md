# AiDescription
使用一个Python脚本用GLM模型生成 简短说明（Description）。

**警告**：代码可能有数个隐藏的问题。

注意到Wiki.js的简短说明实在是难弄，又想要让SEO开心，遂想出来这样一个自动化脚本。

## 主要逻辑
1. 当wiki.js页面被改变，同步到Github仓库。
2. 触发Github仓库变动，激活Github Action。
3. Github Action 访问 https://xxxxxx.xx/xxxx/summary/page_name
4. 激活后端的逻辑，发现此page_name不在 列表' 中，请求AI生成简短说明并覆盖。将本page_name添加到 列表' 。
5. 此时会再次使wiki.js页面被改变，同步到Github仓库。
6. 触发Github仓库变动，激活Github Action。
7. Github Action 访问 https://xxxxxx.xx/xxxx/summary/page_name
8. 激活后端的逻辑，发现此page_name在 列表' 中，跳过生成与替换逻辑，将page_name移出 列表' 。

## 前置条件
1. 脚本使用 https://open.bigmodel.cn/ 的SDK
2. 使用GraphQL接口，需要在Wiki.js打开
3. 环境需要 pip install zai-sdk requests flask

## 食用方法
1. 首先去智谱AI开放平台申请一个API KEY https://bigmodel.cn/usercenter/proj-mgmt/apikeys
2. 下载本仓库的 ./main.py 放到某个位置
3. 调整main.py中的CONFIG
```Python
CONFIG = {
    "ZHIPU_API_KEY": "",
    "WIKI_API_KEY": "",
    "GRAPHQL_URL": "http://localhost:2525/graphql",
    "SUMMARY_KEY": "",
    "ZHIPU_MODEL": "GLM-4.7",
    "ZHIPU_TEMPERATURE": 0.3,
    "ZHIPU_MAX_TOKENS": 3000,  # 增加到3000以支持更详细的总结
}
```
将ZHIPU_API_KEY填入申请的智谱AI开放平台的API KEY

将WIKI_API_KEY填入WIKI.js的GraphQL API KEY

将GRAPHQL_URL填入你的 站点/graphql 。例如 https://xxxx.com/graphql

将SUMMARY_KEY填入一串随机字符

4. 挂着运行这个脚本。他将运行在 0.0.0.0:4050 。设置一个反代，域名任意。
5. 假设你的域名是 https://xxxx.com/ ，你应当反代设置
```nginx
location /{SUMMARY_KEY}/summary/ {
    proxy_pass http://127.0.0.1:4050;
    proxy_set_header Host 127.0.0.1;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_buffering off;
    proxy_cache off;
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
    chunked_transfer_encoding on;
}
```
把SUMMARY_KEY换成上文你设置的随机字符串
6. 如果一切正常，那么此时你访问 https://xxxx.com/{SUMMARY_KEY}/summary/home 将会返回：
```html
data: 主页不能生成总结data: [DONE]
```
7. 将你的Wiki.js与Github仓库连接起来。
8. 设置你的仓库 点击Settings - Security - Actions secrets and variables - Repository secrets - 新建一个
```
NAME: AI_SUMMARY
Value:{SUMMARY_KEY}
```
10. 在仓库内创建 /.github/workflows/ai_summary.yml 将本仓库的ai_summary.yml 复制进去，把 nswiki.cn 换成你的域名 xxxx.com
11. 此时修改一个页面试试看，等到你的 wiki.js 与 Github 同步后，将自动激活接口触发更新描述的逻辑。
