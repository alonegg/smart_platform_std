# WP3 符合性测试工具（首批用例）

面向《智慧教学-数据模型标准》的候选合成联调工具。实现框架、离线 JSON/交换包核验与 T01/T05/T06/T07/T08-P/C/A/R/T09/T10/T11/T23/T25；其他用例均按选择关系输出 skipped 或 not_applicable。**跳过不计为通过**；不是认证、D2 冻结、真实平台数据或完整链路符合性证据。

依赖复用 `验证/契约/requirements.txt`，不新增依赖。所有读入 fixture 只读；合成应用、grant、令牌使用真实 UTC 和独立 UUID 命名域。输出仅写入 CLI 指定路径，请勿指定仓库已提交文件。

```sh
PYENV_VERSION=3.11.18 python3 -m pytest 验证/测试工具 -q
PYENV_VERSION=3.11.18 python3 验证/测试工具/wp3.py list
PYENV_VERSION=3.11.18 python3 验证/测试工具/wp3.py validate 验证/测试工具/tests/fixtures/packages/valid --json
PYENV_VERSION=3.11.18 python3 验证/测试工具/wp3.py run --target inproc:reference --role public-service --profile P-SUB --cases T05 --json-out /tmp/r.json --report-out /tmp/r.md
```

`validate PATH...` 支持 JSON、目录、ZIP，`--target` 与 `--stage input|stored|exchange` 传给 WP1 JSON 校验。单路径直接输出 WP1 格式（另含 path）；多路径输出逐个结果及 result 汇总；退出码 0/1。包内依赖、确定性、独立恢复明确 skipped。

`run` 可重复 `--profile`，`--cases T05,T08-P` 限制执行但不改变适用性；`--grd-stages P,C,A,R` 默认全部，`--trigger Txx` 显式选择并记录原因。HTTP 使用 WP2 路由，管理凭证从 `--admin-token-env`（默认 WP2_ADMIN_TOKEN）读取，不输出令牌。没有管理凭证则跳过，错误/不可解析响应则失败。八个 `inproc:bad:<name>` 反例与本地 HTTP 托管见 [bad_impls/README.md](bad_impls/README.md)。退出码：0 通过，1 不通过，2 未完成。

结果包含 T01—T26 及已登记子用例；父项 T08/T12/T20 标记 container=true，按子用例状态聚合，不重复计数。T08 按指定阶段选择；T20 基本选择展开 F/L/E。case 目录存在 check.py 即发现执行，无硬编码用例白名单。中文 Markdown 包含计数、承担方、交接点、观察点和未覆盖子场景。参见 profiles.json、临时假设.md、scope.json、追溯表.csv。追溯只描述实际行为子集，不把未实现用例算覆盖。

从仓库根运行全部 WP3、追溯及 WP2 回归（一条命令）：

```sh
PYENV_VERSION=3.11.18 python3 -m pytest 验证/测试工具 -q && PYENV_VERSION=3.11.18 python3 验证/测试工具/tools/check_trace.py && PYENV_VERSION=3.11.18 python3 -m unittest discover -s 验证/参考公共服务/tests -v
```

坏实现测试分别执行首批 13 用例，要求 overall=failed、指定观察点由正常响应比较判失败，并禁止任何首批用例因执行异常整体失败；inproc:reference 的同批 13 用例必须全部通过。因为范围外适用项仍 skipped，参考实现的 overall 仍为 incomplete，不伪称完整通过。反例只证明这些合成观察有检测能力，不证明全部缺陷均能检出。
