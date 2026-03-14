# 東京警察病院 英語版ウェブサイト

Hugo + GitHub Pages で構築した東京警察病院の英語版静的ウェブサイトです。

---

## 1. このサイトについて

| 項目 | 内容 |
|---|---|
| サイト名 | Tokyo Police Hospital (東京警察病院) 英語版 |
| フレームワーク | Hugo（静的サイトジェネレーター） |
| ホスティング | GitHub Pages |
| デプロイ | GitHub Actions（mainブランチへのpushで自動） |
| 対象言語 | 英語（English） |

### ファイル構成

```
警察病院英語ページ/
├── hugo.toml                    # Hugo設定ファイル
├── content/                     # コンテンツ（Markdownファイル）
│   ├── _index.md               # トップページ
│   ├── access.md               # アクセス
│   ├── privacy.md              # プライバシーポリシー
│   ├── outpatient/             # 外来情報
│   ├── departments/            # 診療科・部門
│   ├── hospitalization/        # 入院案内
│   ├── about/                  # 病院紹介
│   └── support/                # サポート・相談
├── layouts/                     # HTMLテンプレート
│   ├── _default/baseof.html    # ベーステンプレート
│   ├── index.html              # トップページテンプレート
│   ├── _default/single.html   # 個別ページテンプレート
│   ├── _default/list.html     # 一覧ページテンプレート
│   └── partials/               # パーツ（ヘッダー・ナビ・フッター）
├── static/css/style.css         # スタイルシート
├── .github/workflows/
│   └── gh-pages.yml            # GitHub Actionsワークフロー
└── README.md                    # このファイル
```

---

## 2. コンテンツの更新方法（GitHubウェブで編集）

Hugoやコマンドラインの知識がなくても、GitHubのウェブ画面だけでコンテンツを更新できます。

### ステップ1: GitHubリポジトリを開く

1. ブラウザで `https://github.com/` にアクセスしてログイン
2. このサイトのリポジトリページを開く

### ステップ2: 編集したいファイルを探す

1. リポジトリのファイル一覧から `content/` フォルダを開く
2. 編集したいページのMarkdownファイル（例: `outpatient/first-visit.md`）をクリック

### ステップ3: ファイルを編集する

1. ファイルの中身が表示されたら、右上の **鉛筆アイコン（✏️ Edit this file）** をクリック
2. テキストエディタが開くので、内容を直接編集する
3. Markdownの記法で書かれているため、以下のルールに従う：
   - `## 見出し` → 大見出し
   - `### 小見出し` → 小見出し
   - `**太字**` → **太字**
   - `- リスト項目` → 箇条書き
   - `| 列1 | 列2 |` → テーブル

### ステップ4: 変更を保存（コミット）する

1. 画面下部にスクロールして **"Commit changes"** セクションを探す
2. 変更内容を一言で説明するコメントを入力（例: "Update first visit information"）
3. **"Commit directly to the `main` branch"** を選択
4. **"Commit changes"** ボタンをクリック

### ステップ5: 自動デプロイを確認する

1. リポジトリの **"Actions"** タブをクリック
2. "Deploy Hugo Site to GitHub Pages" ワークフローが実行中または完了しているのを確認
3. 緑色のチェックマーク（✅）が表示されればデプロイ成功
4. 数分後にサイトに変更が反映される

### よくある編集例

**電話番号を変更する場合：** `hugo.toml` ファイルの `phone = "..."` の部分を変更

**お知らせを追加する場合：** `layouts/index.html` の Notice セクションに新しい記事を追加

**ページ内容を更新する場合：** 対応する `content/` フォルダ内のMarkdownファイルを編集

---

## 3. ビルド方法

### 自動ビルド（推奨）

`main` ブランチに変更をpushすると、GitHub Actionsが自動的に：
1. Hugo（Extended版）でサイトをビルド
2. `public/` フォルダの内容をGitHub Pagesにデプロイ

通常はこの自動ビルドのみ使用します。

### 手動ビルド（ローカル確認用）

ローカル環境で確認したい場合：

```bash
# Hugoのインストール（macOS）
brew install hugo

# ローカルサーバー起動（ブラウザで http://localhost:1313 を開く）
hugo server -D

# 本番用ビルド（publicフォルダに出力）
hugo --minify
```

---

## 4. GitHub Pages の設定方法

### 初回セットアップ

1. GitHubリポジトリの **Settings** タブを開く
2. 左メニューから **Pages** をクリック
3. **Source** を **"GitHub Actions"** に設定する
4. ✅ 設定を保存

### BaseURLの変更

公開URLが確定したら `hugo.toml` の `baseURL` を更新する：

```toml
# 変更前
baseURL = "https://your-org.github.io/tokyo-police-hospital-en/"

# 変更後（実際のURLに置き換える）
baseURL = "https://実際のGitHubユーザー名.github.io/リポジトリ名/"
```

### カスタムドメインの設定（任意）

独自ドメイン（例: `en.keishicho-hospital.jp`）を使用する場合：

1. ドメイン管理サービスでCNAMEレコードを設定
2. GitHub PagesのSettings → PagesでCustom domainを入力
3. `static/CNAME` ファイルを作成し、ドメイン名を記載

---

## 5. 技術仕様

| 項目 | 詳細 |
|---|---|
| Hugo バージョン | 0.128.0（Extended版） |
| テーマ | カスタムテーマ（テーマ不使用、layouts/直下に配置） |
| CSS | カスタムCSS（static/css/style.css） |
| JavaScript | 最小限のインラインJS（ナビゲーション、Back to top） |
| 外部依存 | なし（フォント・アイコンはすべて自前） |
| レスポンシブ | 対応（ブレークポイント: 480px / 768px / 992px） |

---

## 6. お問い合わせ先

このウェブサイトの技術的な問題については、病院のIT管理部門にご連絡ください。

**東京警察病院（医療内容に関するお問い合わせ）**
- 電話: 03-5343-5611
- 受付時間: 月〜土 8:00〜17:00

---

*最終更新: 2025年*
