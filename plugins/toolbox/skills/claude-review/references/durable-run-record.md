# Durable review run record

Claude/Codex の review payload は、この契約を実装する host wrapper の内側で実行する。wrapper は provider 固有CLIとは独立させ、同じ lifecycle を使う。

## 最小 schema

```json
{
  "schema_version": 1,
  "run_id": "UUID",
  "provider": "claude|codex",
  "session_id": "UUID|null",
  "state": "prepared|running|exited",
  "cwd": "/resolved/path",
  "target": "/resolved/path",
  "model": "model-id",
  "effort": "level",
  "host_handle": "string|null",
  "process": { "pid": 12345, "started_at": "RFC3339" },
  "paths": { "events": "...", "final": "...", "stderr": "..." },
  "started_at": "RFC3339|null",
  "exited_at": "RFC3339|null",
  "exit_status": null
}
```

## wrapper の手順

1. 新しい run UUID から永続 state root の `reviews/<run_id>/` を導出し、既存なら起動を拒否する。
2. 専用出力fileを排他的に作り、全pathを解決して `prepared` recordを書く。一時fileを同じdirectoryへ書き、flush後にrenameする。
3. CLI子processを起動し、PIDと実起動時刻を取得して `running`へ原子的に更新する。stdout/event、final、stderrは専用fileへ接続する。
4. providerの初期eventからsession IDを検証してrecordへ原子的に追記する。Claudeは採番UUIDとの一致、Codexは`thread.started.thread_id`を確認する。
5. 子processをwaitし、`exited_at`とexit statusを設定した`exited` recordへ原子的に更新して、同じstatusをhostへ返す。signal終了もstatusへ残す。
6. wrapper自身が中断され`running`が残った場合、復旧側はPIDと開始時刻を両方照合する。一致processがなければ終了済み・status不明としてeventとstderrを調べる。

record更新に上書き直書きは使わない。host固有のdurable task metadataが同じschema・原子性・再発見性を保証する場合だけ、それを同等実装として利用できる。
