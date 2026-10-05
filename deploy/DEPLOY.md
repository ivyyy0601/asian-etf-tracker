# ETF 看板：部署与运维

线上地址：**http://91.98.37.33/etf/**

| 项 | 值 |
|---|---|
| 服务器目录 | `/opt/etf-tracker`（属主 `etf` 用户，数据 CSV 也在这里） |
| 网页服务 | systemd `etf-dashboard`，监听 `127.0.0.1:8502`，路径前缀 `/etf` |
| 数据采集 | systemd `etf-collector.service`，由 `etf-collector.timer` 触发 |
| 采集时间 | 周一到周五 **07:00 香港时间**（= 前一天 19:00 美东） |
| 反向代理 | nginx `/etf/`，配置在 `final/server/nginx.conf`（和情绪看板共用） |
| 时区 | 服务器本身是美东时间；香港时区单独写在服务的 `TZ=Asia/Hong_Kong` 和定时器的 `OnCalendar` 里 |

## 本文件夹里的文件

| 文件 | 对应服务器上的位置 | 用途 |
|---|---|---|
| `etf-dashboard.service` | `/etc/systemd/system/` | 常驻运行 Streamlit |
| `etf-collector.service` | `/etc/systemd/system/` | 跑一次：`data_collection.py` 拉数据，再运行 `build_cache.py` 预计算 |
| `etf-collector.timer` | `/etc/systemd/system/` | 周一到周五 07:00 HKT 触发采集 |
| `setup.sh` | — | **全新服务器**一键安装（建用户、venv、装 systemd 服务、首次采集） |

---

## 日常：修改代码后上线

在 `final/` 目录下运行。先预览会上传哪些文件：

```bash
bash server/deploy.sh etf --dry-run
```

确认后正式部署（会自动备份并重启 `etf-dashboard`）：

```bash
bash server/deploy.sh etf
```

只会上传代码和配置 JSON。服务器上的 `data*/` 目录和 `dashboard_cache.pkl` 不会被覆盖。

如果改的是 `deploy/` 里的 systemd 文件，还要复制到 systemd 目录并重载：

```bash
ssh root@91.98.37.33 'cp /opt/etf-tracker/deploy/etf-* /etc/systemd/system/ && systemctl daemon-reload && systemctl restart etf-dashboard etf-collector.timer'
```

## 每日数据流程

```
07:00 HKT  etf-collector.timer ─► etf-collector.service
              ├─ data_collection.py  增量拉 5 个市场的 OHLCV（yfinance，失败时用 AkShare）
              │                      → data/ (港股)、data_ashare/、data_tw/、data_sk/、data_us/
              └─ build_cache.py      预计算 Summary 页面要用的结果 → dashboard_cache.pkl

网页加载时：utils/data_cached.py 先读 dashboard_cache.pkl
            用户选了自定义日期范围（没有缓存）时才现场计算
```

07:00 香港时间亚洲市场还没开盘，美股也已经收盘，所以 5 个市场前一个交易日的收盘数据都是完整的。

---

## 常用命令（在服务器上运行）

```bash
systemctl status etf-dashboard                # 网页服务状态
systemctl restart etf-dashboard               # 重启网页
journalctl -u etf-dashboard -f                # 网页日志

systemctl start etf-collector                 # 立刻手动采集一次
journalctl -u etf-collector -f                # 采集日志
systemctl list-timers etf-collector.timer     # 下一次什么时候跑
tail -f /opt/etf-tracker/data_collection.log  # 采集脚本自己的日志
```

修改采集时间：编辑 `etf-collector.timer` 里的 `OnCalendar=`，部署后运行 `systemctl daemon-reload && systemctl restart etf-collector.timer`。

## 故障排查

| 现象 | 检查 |
|---|---|
| 页面打不开 / 502 | `systemctl status etf-dashboard`，`journalctl -u etf-dashboard -n 50` |
| 资源 404、一直转圈 | service 里是否有 `--server.baseUrlPath=etf`；nginx 的 `/etf/` 是否指向 8502 |
| 数据停在旧日期 | `systemctl list-timers` 看上次运行时间；`journalctl -u etf-collector -n 100` |
| Summary 页面很慢 | `dashboard_cache.pkl` 不存在或太旧 → `sudo -u etf DATA_ROOT=/opt/etf-tracker /opt/etf-tracker/venv/bin/python build_cache.py` |

---

## 从零搭建（新服务器）

只有换服务器时才需要。前提：情绪看板已经按它的 `DEPLOY.md` 装好（nginx 等系统依赖由那边装）。

1. 上传代码到临时目录（在 `etf-tracker/` 下运行）：
   ```bash
   rsync -a --exclude venv --exclude 'data*/' ./ root@<IP>:/root/etf-tracker/
   ```
2. 运行一键安装。它会建 `etf` 用户和 `/opt/etf-tracker`，装 venv 和 systemd 服务，并开始首次全量采集（20–40 分钟）：
   ```bash
   ssh root@<IP> 'bash /root/etf-tracker/deploy/setup.sh'
   ```
3. 确认 nginx 里有 `/etf/` 这一段（见 `final/server/nginx.conf`），然后重载 nginx。
4. 首次采集完成后打开 `http://<IP>/etf/` 检查。
