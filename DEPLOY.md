# DemandRadar 部署手册

一台 2C4G 的 Linux 主机即可承载早期流量。

## 1. 准备

- 装好 Docker Engine 24+ 与 docker-compose 插件。
- 域名解析（A 记录）指向主机公网 IP。
- 复制环境样板：

```bash
cp .env.prod.example .env.prod
$EDITOR .env.prod
```

必填项：
- `DOMAIN` 与 `PUBLIC_BASE_URL`（含 https://）
- `ACME_EMAIL`（Let's Encrypt 提示邮箱）
- `APP_SECRET_KEY`（`python -c 'import secrets;print(secrets.token_urlsafe(32))'`）
- `POSTGRES_PASSWORD`
- 至少一个 LLM 服务商（`DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`）
- `EMBEDDING_API_KEY`

## 2. 初次部署

```bash
# 拉镜像（如果走 GHCR）或本地构建
make prod-build

# 启动整套
make prod-up

# 查看状态
make prod-ps
make prod-logs
```

`api` 容器启动时会自动执行 `alembic upgrade head`；首启会创建全部表 + pgvector ivfflat 索引。

## 3. 验证清单

```bash
# 健康检查
curl -fsS https://$DOMAIN/healthz
# Prometheus（默认仅内网可见，本地或 SSH 隧道 curl 才能拿到）
curl -fsS http://<host-internal>/metrics | head -20
# 前端
open https://$DOMAIN
```

预期：
- `/healthz` 返回 `{"status":"ok","db":"ok",...}`
- 首页 SSR 出实时（或 fallback）数据
- `/login` 输入邮箱后能在 dev 模式（无 SMTP）看到 `debug_link`

## 4. 灰度开通早期用户

```bash
# 给某个 brief 单独发码
make issue-code plan=brief_oneoff days=0 brief_id=42
# 给周报付费用户
make issue-code plan=weekly_pro days=30
```

把输出的 token 邮件给客户即可。客户登录后粘贴到 `/account` 兑换框激活。

## 4.5 国际订阅 / Stripe USD

走信用卡订阅（面向 indie hacker 国际市场）请按
[`docs/STRIPE_USD_SETUP.md`](docs/STRIPE_USD_SETUP.md) 全程操作，含：

- 创建三个 Product / Price（`$9.90/mo` Pro Weekly、`$29/mo` Studio、`$29` Single Brief）
- Customer Portal 与 Stripe Tax 配置
- Webhook 端点（本地用 `stripe listen`，prod 用 `https://<domain>/api/billing/webhook/stripe`）
- 在 `.env.prod` 填入 `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / 三个 Price IDs
- 重启 `api`、按文档第 6 节做生产烟测

留空 `STRIPE_*` 时系统自动降级到「兑换码模式」——`make issue-code` 手动发码即可。

## 5. CI/CD

仓库已配 GitHub Actions（`.github/workflows/`）：

- `ci.yml`：每次 push / PR 跑 ruff + pytest + next build；main 分支推 GHCR 镜像
- `deploy.yml`：手动触发或发 release 自动 SSH 到目标机 `docker compose pull && up -d`

需配置仓库 Secrets：

| Secret | 说明 |
|---|---|
| `DEPLOY_HOST` | 目标机 IP / 域名 |
| `DEPLOY_USER` | SSH 用户名 |
| `DEPLOY_SSH_KEY` | 私钥（PEM 格式） |
| `DEPLOY_PORT` | （可选）SSH 端口 |
| `DEPLOY_PATH` | 仓库部署目录（如 `/opt/demandradar`） |

仓库 Variables 可选：`PUBLIC_BASE_URL`（构建 web 镜像时注入 `NEXT_PUBLIC_API_URL`）。

## 6. 监控告警

- **Sentry**：把 DSN 放到 `.env.prod` 的 `SENTRY_DSN`，重启后立即上报。`SENTRY_TRACES_SAMPLE_RATE=0.05` 表示 5% 请求采样追踪。
- **Prometheus**：`/metrics` 暴露 4 个核心指标族：
  - `demandradar_http_requests_total`（按 method/path/status）
  - `demandradar_http_request_duration_seconds`（直方图）
  - `demandradar_http_in_flight`（瞬时并发）
  - `demandradar_job_runs_total` + `demandradar_job_duration_seconds`（后台任务）

  默认 Caddy 配置只允许内网访问 `/metrics`；在同主机部署 Prometheus 即可抓取。

- **结构化日志**：API/worker 容器 `LOG_FORMAT=json`，每行一个 JSON 对象，含 `request_id` 字段。可直接接 Loki/Promtail 或 ELK：

  ```bash
  docker compose -f docker-compose.prod.yml logs --no-color api | head -3
  ```

## 7. 回滚

```bash
# 上一个版本镜像 sha 假定为 <SHA>
TAG=<SHA> make prod-up
# 或者直接 ssh 到机器执行
TAG=<SHA> docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

只有 web/api/worker 会被替换，PG/Redis 数据卷与 Caddy 证书都不动。

## 8. 备份

最关键的两份卷：

```bash
# Postgres
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U $POSTGRES_USER $POSTGRES_DB | gzip > "backup-$(date +%F).sql.gz"

# Caddy 证书
docker run --rm -v demandradar_caddy_data:/c -v $(pwd):/out alpine \
  tar czf /out/caddy-$(date +%F).tgz -C /c .
```

建议挂 cron 每日打包 + 上传 OSS / S3。

## 9. 故障排查速查

| 现象 | 第一步排查 |
|---|---|
| 网站 502 | `make prod-logs` 看 caddy；`docker ps` 看 web/api 是否 healthy |
| `/healthz` 503 db down | `docker exec -it postgres psql ...` 验证连通；检查磁盘 |
| 后台任务不跑 | `docker compose logs worker` 找 `scheduler started` 行 |
| 前端 SSR 报 ECONNREFUSED | 检查 `INTERNAL_API_URL=http://api:8000` 是否注入 web 容器 |
| 登录链接点开 400 expired | 客户邮箱链接过 15min；让其重新发起 |
