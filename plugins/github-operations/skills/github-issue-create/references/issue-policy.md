# Issueのpolicy

- Issueを作業の正本として扱い、Projectをrepositoryをまたぐ優先順位の待ち行列として扱う。
- owner、repository、Project、field、option、labelは、現在のGitHubの状態から解決する。
- Issueのタイトルと記述は、自律的に起票する後続課題を含め、既定で日本語にする。ユーザーの明示的な言語の指定と、対象repositoryの明示的な言語の規約を優先し、衝突はapplyの前に解決する。templateのkey、識別子、label、引用したログは原文のまま保つ。英語の例や既存のIssueがあるだけでは、既定を上書きしない。正本はskill本体の「Issueの出力言語」の節である。
- 安定した操作のfingerprintを内部で生成し、本文に加える。呼び出し側が選んだfingerprintは受け付けない。冪等性を、検索のindexだけに頼らない。
- Projectへの登録を試みる前に、作成したIssueのURLを記録する。
- 結果が分からない書き込みの後は、無条件に再試行せず、読み取って突き合わせる。
