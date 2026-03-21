# Global Market Monitor

日本在住の個人投資家向けに作った Python 製の市場監視アプリです。  
株式、セクター、債券、コモディティ、為替などの複数指標をまとめて確認し、相場の地合いと追加投資の判断材料をレポートとして出力します。

## Features

- 複数アセットの市場データを定期取得
- レジーム判定、サイクル判定、合成スコア算出
- セクター比較と資産クラス比較
- 追加投資タイミングの補助シグナル生成
- Markdown / HTML レポート出力
- 履歴をまとめたダッシュボード生成

## Quick Start

```bash
python -m pip install -r project/requirements.txt
python project/main.py
```

詳しい構成、実行方法、出力内容は [project/README.md](project/README.md) を参照してください。

## Notes

- この公開版にはローカルのログ、キャッシュ、生成済みレポート、個人用メモは含めていません。
- 環境依存の絶対パスは公開向けに汎用化しています。
