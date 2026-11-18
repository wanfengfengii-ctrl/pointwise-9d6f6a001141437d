# 澄湾带材表面检测核账

澄湾带材厂的检测头按原拍提供有符号偏差。站端值班员将每卷绑定到固定检测口径，核对原拍并独立封存班段。质控室收到交班件后可断开站端录制，签发整卷告警。现场复查员凭报告号取得需复查的原拍位置与签发回执。

## 运行

在项目根目录使用 Python 3.11。工程只使用标准库及其 SQLite 支持。运行平台提供的完整回归入口和样例如下。

```shell
python3 -B check_project.py
python3 -B demo.py sample/roll.json
```

完整套件也可以通过 `python3 -B -m unittest discover -s tests -t . -v` 运行。回归用独立临时目录和真实 SQLite。样例在临时目录封记两班并导出交班件，移除该临时站端后签发并按号导出。阈值为 5。第 1 拍累计为 4，第 2 拍加 2 后告警清零，第 3 拍减 1 后截为零。样例输出同时展示实际签发和交付结果。

## 口径和数据

预期录制、交班件和整卷覆盖都用包含首尾的整数原拍闭区间。输入可以乱序到达。每个录制覆盖内，各原拍恰好出现一次。偏差单位为 `du`。公开有理值接口接受 `Fraction`、整数、精确分数字符串、有限十进制字符串及整数分子与正分母的二元组。浮点值、布尔值、零分母和缺值被拒绝。持久和交付中的有理值以最简整数分子和正分母表示。

固定计划阈值为 `H > 0`。每拍从合法累计量 `0 <= s < H` 开始，加上有符号偏差，负值截为零。累加结果达到或超过 `H` 时在该原拍告警，随后将累计量清为零。其余情况原值传给下一拍。零偏差和空告警均有效。整卷只在开场取零。指定同一固定录制的等价切段得到相同的告警和期末量。签发号及回执号在每次签发时生成。

## Python 接口

1. `plans.assignments.initialize_plan_store(path)` 初始化站端计划表。`register_plan(path, roll_id, plan_id, revision, unit, threshold)` 原子登记计划修订并绑定卷，返回 `RollAssignment`。`resolve_assignment(path, roll_id)` 按卷读取。已绑定卷重复登记相同内容保留原引用，同修订异内容或同卷改绑均拒绝并回滚。新修订可用于新卷。
2. 在同一站端路径构造 `recording.ledger.RecordingLedger(path)` 并调用 `initialize()`。用 `recording.segments.seal_recording(ledger, recording_id, roll_id, coverage, rows)` 固定录制。`coverage` 为 `recording.sequence.TickCoverage(first, last)`。每行包含 `roll_id`、`plan_id`、`revision`、`unit`、`tick` 和 `deviation`。`detector.trace.preview(ledger, recording_id, entry=0)` 返回 `TraceResult`，其中 `alarms` 为原拍元组，`amount` 为 `Fraction`。
3. 在站端路径构造并初始化 `evidence.publish.SegmentStore(path)`。`publish_segment(recordings, store, recording_id, evidence_id, coverage)` 选取封记录制中的连续子段并固定 `SegmentEvidence`。相同号和相同内容可重报。`evidence.export.export_segment(store, evidence_id, destination)` 导出该固定件，并返回同一载荷字节。固定件包含卷、计划、来源录制号、覆盖和班段响应。逐拍偏差留在站端。
4. `reports.accept.accept_segments(assignment, coverage, payloads)` 接收固定任务的 `RollAssignment` 和预期整卷覆盖，以及本次明确选定的交班件字节序列。任务口径来自预先固定的检验任务。接纳时比较完整计划修订和卷身份，检查首尾及每个接缝，按原拍整理。不同录制可贡献同卷的相邻班段。
5. 报告端在自己的路径构造 `archive.commit.ArchiveStore(path)` 并调用 `initialize()`。`reports.issue.issue_report(archive, assignment, coverage, payloads)` 接纳并核算指定件，将报告和成功回执一起提交，返回 `IssuedReport`。结果含固定计划、覆盖、告警、期末量和原拍顺序的交班件引用。引用包括件号和规范载荷的 SHA-256。
6. `archive.read.read_report(archive, report_id)` 返回 `ReportLookup`。`found=True` 时 `report` 含原签发结果和回执。未知号得到 `found=False` 和 `report=None`。`archive.export.export_report(archive, report_id, destination)` 生成现场交付 JSON，返回带原号及载荷的 `ReportDelivery`。

各初始化入口可重复执行并保留已存数据。录制与交班件未知号通过 `KeyError` 表示。无效业务输入通过 `ValueError` 表示，其中覆盖缺口或相交通过 `CoverageError` 表示。SQLite 写入及提交错误向调用方传播。业务拒绝和事务失败均不留新的固定成果或成功回执。导出在目标的父目录生成临时副本并原子替换目标，未知编号或导出失败时保留原固定件及已有目标。导出目标的父目录须已存在。

## 交班件格式

`evidence.codec.encode_segment` 和 `decode_segment` 读写 UTF-8 JSON 固定件。版本为 `1`。`binding` 包含卷、计划、来源录制号及覆盖，`response` 包含阈值和按入量排列的 `pieces`。每一项以 `start`、`stop` 给出半开区间，告警用 `alarms` 给出，出量由 `slope * entry + intercept` 表示。斜率为 0 或 1，区间紧密覆盖 `[0,H)`，告警位于声明覆盖内。`detector.response.evaluate_response` 可用任意合法精确入量独立核对一个固定班段。报告领取直接读取已归档快照和回执。
