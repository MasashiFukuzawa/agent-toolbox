---
name: e2e-capability-verification
description: >-
  staging や test 環境で認証付き E2E と機能可否を安全に検証する。破壊的操作や storageState が関わる検証に使う。アドホックなブラウザ操作には browser-operations を使う。「stagingで可能か確認」「認証付きE2Eを検証」を正のトリガーとし、日常的なサイト閲覧やログイン引き継ぎには使わない。
---
# E2E機能検証

UI automationやstagingでWeb appを検証する。機能が見当たらない、dataを変更し得る、または認証済みbrowser stateが必要な場合に特に適用する。

**振り分け**: repositoryのE2E wrapper、staging検証、破壊的flow gateには本Skillを使う。アドホック操作、tool選択、協調ログイン、repositoryをまたぐ個人sessionには `browser-operations` を使う。

## 必須ガードレール

browser-operationsのガードレールを前提にする。日常用ブラウザのprofileとエージェント用profileの分離、profile dirと取得物（`.playwright-cli/`、snapshot、screenshot、trace、video、network log）を認証情報に準じて扱うこと、パスワード・token・cookieをプロンプトへ貼らせないことは、そちらに従う。検証に固有の規則は次のとおり。

- 見えているUIだけで「できない」と結論しない。code・API側の根拠を少なくとも1つ確かめる（route、共有schema、生成されたOpenAPI、test、DB schema、networkの呼び出し）。
- 「操作する手段が見えない」と「機能が無い」を分ける。どちらの証拠を持っているかを言う。
- stagingは、ユーザーがtest dataを変更してよいと明示しない限り、本物のdataとして扱う。
- 最小権限の、staging・test専用のユーザーを使う。本番のsessionでエージェントのE2Eを動かさない。
- Playwrightの `storageState` ファイルは認証情報として扱う。cookie・localStorage・tokenの中身を、出力・貼り付け・要約・commit・閲覧しない。プロンプトへ貼るよう頼むこともしない。
- 認証済みのbrowser stateがあるなら、隔離したcontextを通してだけ再利用し、操作の前にユーザーとテナントを確かめる。
- secretが足りない時は、ローカルのwrapperか認証のsetupをユーザーに実行してもらう。
- repoがE2E wrapper、metadataのprecheck、auth stateのvalidator、runbookを用意しているなら、それを正とする。素のPlaywright CLI、素のPlaywright MCP、その場のブラウザsession、個人の永続Chrome profileで迂回しない。
- repoが認証setupにsecret注入のwrapper（1Password Environmentsなど）を定めているなら、認証済みstateの生成にはそのwrapperだけを使う。secretの値を手でexportしない。wrapperを作り直さない。元のユーザー名・パスワードを尋ねない。
- 認証済みstagingのstateを、Playwright CLIへ素の経路（stateコマンド、CLIの設定、環境変数、永続profile、独自profile、stdoutへの出力）で読み込ませない。metadataのprecheck、外へ出さない出力の扱い、policyの検査を備えたwrapperをrepoが用意している場合だけ使う。
- 無人のE2Eでは、人が承認するローカルのsecretより、repoのCI標準のsecret storeとworkload identityの経路を優先する。
- E2E用のidentityの変更がIAM、境界、secret store、deployのstackをまたぐなら、infraの変更として扱う。app側のtestやworkflowを変える前に、stackをまたぐapplyの順序をrepoのrunbookで確かめる。

## token効率のよいworkflow

1. 小さな検証の表を決める：表示、正常系、エラー系、永続化、cleanup、必要なら認可。
2. UIを広く探る前に、`rg` でcodeを調べる：route、mutationのhook、ボタンの文言、API client、test。
3. ブラウザのtoolを選ぶ前に、repoの文書とscriptから標準のwrapperを探す：`docs/agents/profile.md`、`AGENTS.md`、E2Eのrunbook、`package.json`、Playwrightの設定、script。
4. 認証付きのstaging E2Eでは、ブラウザを開く前に、下のpreflightを行う。
5. UIのtoolは範囲を絞って使う。
   - 通常の認証付きstaging E2E：repoが用意したPlaywright MCPのwrapper（あれば）。
   - 繰り返す流れ、screenshot、trace、assertion：repoが用意したPlaywrightのscriptか `@playwright/test` のコマンド。
   - Playwright CLI：認証不要の確認か、repoがwrapしている探索だけ。認証付きstagingに、素のCLIのstorage・profile・stdoutの経路を使わない。
   - 素のPlaywright MCP・素のPlaywright script：repoのwrapperが無い場合だけ。認証付きなら `--isolated` と明示したauth stateを使う。
   - Chrome DevTools：失敗を深く調べる必要が出た後の、console・network・性能・source map・memoryのdebug。
   - 画面を直接操作する手段、または人への引き継ぎ：人が行うしかないログイン、MFA、SSO、画面でしか確かめられない条件があり、ブラウザの自動操作が現実的でない場合だけ。
6. accessibility treeやDOMの全体を出さず、狙ったselector、network requestの要約、screenshotを使う。
7. 記録するのは要点だけにする：URL、表示されたユーザー・テナント、行った操作、requestのstatus、見えた結果、作ったscreenshotのpath。
8. 長いE2Eは、流れをscriptにして、短いJSONかMarkdownの報告を出す。

## 認証付きE2Eのpreflight

認証付きのstaging・ブラウザE2Eの前に行う。

1. repoのprofile・runbook・scriptの名前を読む。secretを含むファイルは読まない。repo標準のmetadataやprecheckのscriptがあれば、それを使う。
2. repo標準のauth stateのpath（多くは `playwright/.auth/staging-user.json`）を、中身を読まずに探す。
3. auth stateのpathがgitignoreされている（または版管理の外にある）ことを確かめる。
4. `*.meta.json` のようなmetadataやvalidatorのscriptがあるなら、`storageState` を調べる代わりにそのprecheckを実行する。
5. stateのファイルが無ければ、package scriptと文書から認証setupのコマンドを探す（`e2e:auth:staging`、`test:e2e:auth`、`auth.setup` など）。
6. repoが認証setupにsecret注入の仕組みを定めているなら、secretでない前提だけを先に確かめる：CLIが使えること、必要な環境・項目の識別子、repoのwrapperの名前。secretの値は調べない・出力しない。
7. repo標準の認証setupは、文書にあるwrapperを通してだけ実行する。wrapperが子のPlaywrightプロセスへsecretを注入してよいが、エージェントはその値をwrapperの外へ出力・記録・保存・受け渡ししない。
8. secret store、ローカルのCLI、アクセス権が無くて認証setupを実行できないなら、その前提を整えるか、wrapperをローカルで実行するようユーザーに頼む。生の認証情報は求めない。パスワードの入力要求、`.env`、個人のChrome profile、secretの手動exportへ下がらない。
9. 認証付きE2Eが、ログイン画面へのredirect、認証済みのはずのAPIからの401/403、ユーザー表示の欠落、session切れの症状で失敗したら、アプリの不具合と扱う前に、auth stateを1回作り直す。
10. auth stateを読み込んだ後、dataを変える前に、表示されているユーザー・テナントか、安全なidentityのendpointで確かめる。

通常はrepoのwrapperを使う。wrapperが無ければ、Playwright MCPかPlaywrightのscriptを、隔離したbrowser contextと明示したstorage stateで使う（考え方としては `--isolated --storage-state=<repo-auth-state>`）。個人の永続Chrome profileを、認証済みstateの既定にしない。

## session永続化とprofile戦略

検証ではない閲覧で、ユーザー自身のログインをrepoをまたいで残したい場合は、ここではなく `browser-operations` のサイトごとのprofileを使う。検証では、ブラウザのtoolを開く前に永続化の方式を選ぶ。判断の順は次のとおり。

1. **repoがwrapperかrunbookを用意している**：それを正とし、その方式（storageState、MCPのwrapper、認証のscriptなど）に従う。以下の2〜4は読まない。
2. **既定：storageStateのファイル＋最小権限の専用アカウント**。`--isolated --storage-state=<repo-auth-state>` で読み込む。これを基準にする理由:
   - 隔離したcontextは、エージェントの普段の環境からcookie・localStorage・tokenを持ち込まない。
   - ファイルは範囲のはっきりした認証情報になる：gitignoreされ、ローカルにだけあり、失効でき、metadataのprecheckや有効期限の検証を行うrepoのwrapperと両立する。
   - 作り直しは認証setupのコマンド1つで済み、session間でbrowser profileの状態が積み上がらない。
3. **永続のuser-data-dir（専用profile）**：次のどれかに当たる場合に*だけ*使う。
   - SSO・MFA・IdPのredirectが生きたbrowser sessionを要求し、storageStateの作り直しが頻繁に壊れる。
   - 手動ログインが避けられず、storageStateの作り直しが作業の実害になるほど頻繁である。
   - browser拡張や、端末の信頼の永続化が技術的に必要である。
   - 採る場合は、**日常用のブラウザと物理的に別の専用dir**（例：`~/.mcp/<agent>-profile`）を使う。repoが専用のtestアカウントを定めているなら、profileをそのアカウントだけに結び付ける。
4. **無人の品質ゲート**：CI標準のsecret注入とworkload identityを使う（次節）。ローカルのstorageStateやuser-data-dirをCIへ持ち込まず、job内でCIのsecret storeからstateを作る。

**人のログインをどこまで許すか**:

- 人がその場にいるローカルの確認：ローカルのwrapper（OSのkeychain、secret管理のCLIなど）でstorageStateを作り、`--storage-state` でエージェントへ渡す。
- 自動化できないSSO・MFA：手動ログインの部分だけ、画面を直接操作する手段か人への引き継ぎで行う。認証が済んだら、storageStateか永続profileを取り、同じsessionの以後の自動操作に使う。
- 無人のCIゲート：人は関与しない。workload identityでsecretを取り、job内でstateを作る。

## 無人E2Eとinfra境界の変更

人がその場にいる開発中の確認には、ローカルのsecret wrapperを使う。無人の品質ゲートには、CI標準のsecret注入とworkload identityを使う。人の承認を待たずに続けられ、生の認証情報をプロンプト・ログ・repositoryに出さずに済む。

E2Eの認証情報、ブラウザtestのworkflowのidentity、secretへのアクセス、networkの境界、deployのstackの信頼規則を変える時:

1. repoのE2E runbookとinfraの依存関係の案内を先に読む。
2. identityを持つstack、アクセスを与えるstack、それを使うstackを特定する。
3. 信頼規則が、別のstackの作るidentityを参照しているなら、関連PRをmergeする前に、必要なapplyの順序を確かめる。
4. 失敗の症状がブラウザのE2E jobに出ているというだけで、app側だけの変更として扱わない。
5. 正しいapplyの順序が分からなければ、実装の前にinfraのレビューを求める。

## 機能切り分けchecklist

機能が無いように見える時:

- UI：見えるボタン・メニュー・dialogはあるか。role、状態、viewport、選択中の項目で隠れていないか。
- API：routeやmutationのendpointはあるか。どのstatus codeと認可が適用されるか。
- Schema・DB：既存のFK、cascade、論理削除、監査の保持、テナント分離のもとで、その操作は安全か。
- Test：その経路を証明する、または意図的に除外しているtestはあるか。
- 製品の境界：MVPの後片付け・管理者向けの操作か、利用者向けの流れか。

このchecklistを終えてから、次のどれかを言う。

- 「UIの操作手段があり、動く」
- 「API・codeに機能はあるが、UIの操作手段が無い」
- 「UI・API・schema・testのどこにも、機能の証拠が無い」
- 「製品・security・dataの整合性の境界によって、意図的に塞がれている」

## 破壊的flowのガードレール

stagingでの作成・更新・削除の前に行う。

1. 状態を変えない確認を先に行う。
2. cleanupの経路を先に特定する：UIでの削除、APIでの削除、DBに安全なfixtureのcleanup、またはdataを残すことへのユーザーの明示的な承認。
3. repoの、状態を変えるflowのgate runbook（または同等のpolicy）を探す。cleanupの経路と、gate runbookか「残るdataのriskを受け入れる」というユーザーの明示的な承認の両方が揃わない限り、flowを実行しない。
4. dataを作るなら、合成のtestだと分かる印を付け、cleanupの経路を確かめる。
5. dataを消すなら、対象と、依存するdataの挙動を正確に確かめる。
6. 事後の状態は、toastの表示だけでなく、UIとnetwork・APIの両方で確かめる。
7. cleanupに失敗したら、安全な範囲の残存metadataと、escalationの経路だけを、すぐに記録する。

## 証跡の扱い

- 次のものを共有しない：取得物、trace、screenshot、network log、cookie、token、`storageState` の中身、生のPIIを含むrequest/responseのbody、providerの生のpayload、OCRの全文、非公開のobject key、署名付きURL。
- 証拠が要る時は、無害化した事実にまとめる：routeのpath、status code、見えた状態、安全なobjectの種類とid、印、失敗の分類。
- 機微な取得物はローカルに留める。Issue、PR、チャット、CIのartifact、最終報告へ出さない。repoのrunbookが無害化した取得物の種類を明示的に許している場合だけ出す。

## 失敗の切り分け

認証付きE2Eが失敗した時:

- 認証・session：auth stateを作り直して1回やり直す。まだ失敗するなら、stagingのE2Eユーザー、権限、テナントの対応、認証setupに人の確認が要ると報告する。
- UI：screenshotと、見えた状態の短い記述を取る。DOM全体ではなく、selectorと見えるlabelを使う。
- console・network：status code、routeのpath、エラーの種類をまとめる。requestのbody、token、cookie、生のPIIは含めない。
- 認可・API：UIが誤りだと結論する前に、route、共有schema、認可のpolicy、生成されたOpenAPI、test、networkのstatusを調べる。
- 性能・source map・memory：Playwrightの証拠がそこを指した後に、Chrome DevToolsで深く調べる。
