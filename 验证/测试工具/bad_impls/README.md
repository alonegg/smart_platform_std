# 故意注入单类缺陷的合成参考服务

这些 Service 子类只用于检查 WP3 能否发现反例，不是替代参考实现，不得用于真实数据或生产系统。均继承 WP2 Service；不修改 WP2 源码，每个类只改变一类边界。其余鉴权、事务、时钟和路由继续复用 WP2。

| 注册名 | 故意缺陷 | 条款/要素 | 必须判失败的用例/观察点 |
|---|---|---|---|
| dup-not-deduped | duplicate 回执后仍多存一条新事实 | 7.6；OBJ-029、FLD-EVT-023 | T05 / T05-02（facts 不再为 1） |
| conflict-overwrite | 同键不同摘要按新事件受理，覆盖原事实 | 7.6.2；OBJ-029、FLD-EVT-020、FLD-EVT-023 | T05 / T05-03（非 conflict、无隔离且原内容改变） |
| service-confirms-grade | 放过服务 grade.confirm 授权及人员确认边界 | 7.5.2、9.2.4、9.5；OBJ-034、OBJ-044、EVT-019 | T08-P / T08-P-confirm-grant（非法授权 accepted）；另有实测确认 accepted 的单元测试 |
| revocation-ineffective | 授权查询忽略 revoked，但仍检查有效期及目录状态 | 8.6.6、9.2；OBJ-044、EVT-003 | T11 / T11-revoked-token（旧令牌 accepted） |
| unapproved-method-allowed | 以登记存在冒充当前方法批准，未批准/暂停均放行 | 10.13.3、10.13.6；OBJ-040、OBJ-041、FLD-MTH-012 | T10 / T10-unapproved（allow=true），T10-history（暂停仍放行） |
| receiver-fields-writable | 接受并保存客户端 event_id/received_at/auth_context | 5.3.3、7.2.3、7.2.4；FLD-EVT-001、FLD-EVT-021、FLD-EVT-022 | T25 / T25-auth_context、T25-event_id、T25-received_at（accepted） |
| proposal-in-formal-view | 将 proposed 项加入正式视图 | 7.5、9.5；OBJ-034、EVT-018 | T08-P / T08-P-proposal-view（formal_count=1） |
| cross-instance-pseudonym | 假名解析不检查记录所属实例 | 11.5.3；OBJ-001、OBJ-042 | T11 / T11-cross-instance（跨实例解析 accepted） |

测试对八个实现分别运行全部首批 13 用例，断言指定观察点正常比较得到 failed；拒绝将执行异常当作缺陷命中。额外测试服务凭证确实能确认，以及三个客户端权威字段确实被保存。一个 HTTP 反例复用 WP2 ReferenceHTTPServer，在端口 0 的线程中运行全部首批。

进程内可使用 `wp3.py run --target inproc:bad:conflict-overwrite ...`。

从仓库根启动 HTTP：

```sh
PYENV_VERSION=3.11.18 python3 验证/测试工具/bad_impls/serve.py conflict-overwrite --port 8701 --bootstrap
```

只绑定 `127.0.0.1`；省略 `--bootstrap` 不打印合成管理员令牌。`--port 0` 自动分配端口。按 WP2 同样的方式，将本次合成管理员令牌放入 WP2_ADMIN_TOKEN 环境变量，再以 `--target http://127.0.0.1:8701` 运行 WP3；不得把凭证写入报告或提交。

实现口径：服务确认反例只绕过 AccessGrant 中 grade.confirm 的禁止项及相应人员确认检查，其他字段仍验证；接收端字段反例先校验剩余合法业务输入，再把客户端专属字段写回保存，故意构造存储契约违规。见 W3-07。坏实现不是标准问题或 WP2 缺陷的证据。
