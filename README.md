# running-gear

名古屋しゃちほこトライアル「おすすめランニングギア」ページ（Amazonアフィリエイト）。

- `index.html` … 表示ページ（新着順/古い順、カテゴリー絞り込み、キーワード検索）
- `products.json` … 商品データ。更新はこのファイルだけを編集する

## 更新ルール（週2回の自動更新用）
- アソシエイトID：`rungenic-22`（リンクは index.html が自動で付与）
- 1回につき3〜5商品を `products` の末尾に追加し、`updated` を当日の日付にする
- 項目：`id`（連番 p020…）、`added`（YYYY-MM-DD）、`category`（`categories` のどれか）、`name`、`comment`（自分の言葉で1〜2文）、`query`（Amazon検索語）
- ASINをAmazonの商品ページで確認できた場合のみ `asin` を入れる。確認できないものは入れない（検索リンクになる）
- 価格・在庫・レビュー数は載せない。他サイトの文章をそのまま写さない
- 既存商品と同じものは追加しない

## 商品画像（Creators API）
- `.github/workflows/fetch-images.yml` が毎日6:17と products.json 更新時に `scripts/fetch_images.py` を実行
- ASIN 未設定の商品は検索で一致したものに `asin` を自動設定し、`image`・`url` を毎日取り直す（手で書かない）
- 認証情報は GitHub の Secrets（AMAZON_CREDENTIAL_ID / AMAZON_CREDENTIAL_SECRET）、資格情報バージョン v3.3
- 利用資格（直近30日の発送済み10件）を失うと画像は自動で消え、イラスト表示に戻る
