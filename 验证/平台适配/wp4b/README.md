# WP4b：平台适配与损失量化

使用 [WP4a](../README.md) 实际部署产生的合成课程与学员导出，按 [WP1](../../契约/README.md) 生成候选投影并逐条校验。真实导出是**事实来源**；本地 Schema 检查和离线诊断包往返不等于真实互操作、校级受理、D2 冻结或符合性声明（4.4.5）。

## 运行

Python 3.11+。从仓库根目录先安装锁定依赖：`python3 -m pip install -r 验证/契约/requirements.txt`。离线测试：

```sh
python3 -B -m pytest 验证/平台适配/wp4b -q -p no:cacheprovider
```

生成候选输入、诊断包与损失报告：

```sh
python3 -B 验证/平台适配/wp4b/run.py
```

默认输出到新临时目录，终端打印路径；可传 `--output` 指定一个尚不存在的目录。命令只读已提交样本，按 WP4a 文件库存复核字节数和 SHA-256。无需 Docker、联网、登录或公共服务。逐要素 CSV 只读复验，不重写已提交副本。

## 输入与输出

| 输入 | 保留或转换 | 不推断 |
| --- | --- | --- |
| Open edX OLX 与表 | 课程键与两个 run 分开；课程树/定义字节，静态文件字节、MIME、长度及 SHA-256；历史成绩的原生版本指针 | 两个 run 不是两个已确认的课程版本；不把当前 OLX 回填旧作答 |
| Open edX tracking / xAPI / Caliper | tracking 作答和 ORA 提交投影；播放信号；ERB 外部标识、主体、动词、对象、时间只作旁证 | transport ID 不当学校事件 ID，协议派生不另计业务事件；不从 play/pause 拼有效观看区间 |
| Open edX ORA、成绩历史 | 两份 UUID 对应的作品字节与原生状态，保留覆盖分历史 | 不从重复的尝试计数生成两个任务尝试，也不把重置当自助撤回 |
| Moodle 两份 .mbz | 同一开课两份快照，模块/章节关系和资源字节；校验原生 SHA-1 后计算 SHA-256 | 不把备份时间/摘要当有效课程版本；第二开课来自表导出，没有自己的 .mbz |
| Moodle 日志、答题、作业、成绩历史 | 作答步骤、任务开始/资源查看与正式提交投影；重开后的作品与分数轨迹 | 不把当前成员当提交时成员，不把 gradebook 历史当决定链 |

按平台输出：

- `candidate-passed.json`：通过未改动的 WP1 校验器的普通 input 记录；`validation-passed.json` 保留校验结果、来源和要素。三条 Moodle 作答均是离线 input，不是已入库事件。
- `candidate-blocked.json`：独立诊断区。候选对象/事件未满足的字段保持**省略**，而非填 null/默认值；`missing_fields` 提取结构性缺失，`gaps` 补充业务原因，完整 WP1 结果保留。不得投递。
- `native-evidence.json`：不能可靠表达为候选对象或事件的原生事实、关联与来源定位；记录库存不等于每个原生动作均实施了转换。
- `diagnostic.zip`：上述投影、证据与实际文件字节。独立离线读回器核验成员集合、SHA-256、字节数；学校授权和签名不在核验范围。随附的 `manifest-attempt.json` 记录真实文件清单子集及预期 WP1 拒绝，不是有效 manifest。
- [loss.csv](loss.csv) 同时是要素→产出文件追溯表；[differences.csv](differences.csv) 只列样本与静态潜力不一致项，解释见[损失报告](损失报告.md)。

## 候选约定与未决事项

沿用 WP1 已登记的候选规则（E12/E24/E26），不新增标准线格式或临时业务规则。E13 未实施 stored/exchange 摘要；压缩包完整性 SHA-256 与 E13 业务摘要无关。

`urn:wp4b:…` 是从原生表键、课程键或 UUID 派生、仅限本次语料的本地对账键；`wp4b-offline/1` 仅标明原型转换配置，非学校批准的 Profile。Moodle 作业 0 基计数转换为候选契约的 1 基表示，原数字和原记录身份均保留。Moodle 作答以源端持久化答题步骤数据行作为事实；input 的 `source_event_id` 只是该原生行主键在适配器命名空间下的投影，不是 Moodle 原生事件 ID 或学校事件 ID。Open edX tracking 和历史表按课程、用户、问题、尝试计数、同秒与同答案保守对账；不把历史行主键、ORA UUID 或日志行号写作 tracking 的源事件 ID（E12）。

适配器不作权威身份、修读或授权登记（E12/E23a）。主体/尝试/作品的结构化引用即使通过，也未证明被引用实体符合契约；三条作答没有已登记的 `source_instance`，因此不能送入校级接收。若要冻结旧数据接入方案，建议由维护机构按 E12/E23a/E26 评审并登记到 WP1，详见[损失报告](损失报告.md)。
