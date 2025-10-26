# Windows 7 バックアップ ZIP 抽出ツール

Windows 7 のバックアップ ZIP セット（`Backup files N.zip`）からファイルを抽出・復元するための、シンプルで保守性の高い Python 3.x スクリプトです。内部ディレクトリ構造を保持し、分割されたパーツを正しい順序で連結して、テキスト形式のサマリーログを出力します。

## 要件

- Windows 上で動作する Python 3.x。
- 外部依存は不要（標準ライブラリのみを使用）。

## 使用方法

このリポジトリのルートから実行するか、スクリプトへのフルパスを指定して実行してください。

- バックアップ ZIP が入ったディレクトリを指定する例:
  `python winbak_extract.py --dir "C:\\Backups"`

- 複数の ZIP を明示的に指定する例:
  `python winbak_extract.py --files "C:\\Backups\\Backup files 1.zip" "C:\\Backups\\Backup files 2.zip"`

- ファイル名のエンコーディングを指定する例（ZIP エントリが UTF-8 でない場合に使用）:
  `python winbak_extract.py --encoding cp932 --dir "C:\\Backups"`
  - ZIP エントリに UTF-8 フラグが立っている場合は常に UTF-8 を使用します。
  - UTF-8 フラグが立っておらず `--encoding` を指定した場合は、そのコーデックでデコードします。利用可能なコーデックは Python ドキュメントの [Standard Encodings](https://docs.python.org/3/library/codecs.html#standard-encodings) を参照してください。
  - UTF-8 フラグが立っておらず `--encoding` が指定されていない場合は、ZIP 仕様に従って CP437 を使用します。

## 動作概要

- ファイル名が `Backup files N.zip`（大文字小文字を区別しない）にマッチする ZIP ファイルのみを対象とし、`N` による自然ソートで処理します。
- 各 ZIP エントリは一時ディレクトリにストリーミングで展開されます: `<dest>\\.winbak_tmp\\<internal_path>\\<name>.part_0001...`。
- 同一の相対パスは大文字小文字を区別せずグループ化され、順にパーツとして扱います。
- パーツの結合はまず `copy /b` を試み、失敗した場合は Python 実装のフォールバックで連結します（順序は ZIP のソート順に従います）。
- 上書きポリシー: 最終出力が既に存在する場合はそのファイルをスキップし、エラーを記録します（上書きしません）。
- 重複ファイルはデデュープせず、敢えてパーツとして連結します（仕様どおり）。
- マージ成功後はステージ済みのパーツファイルを削除します。
- パーツが単一の場合は、コピーではなく直接移動を行いサイズ検証を実施します（パフォーマンス最適化）。
- マージ結果・パーツ数・スキップ・エラーを含むタイムスタンプ付きサマリーログ `winbak_extract_summary_YYYYMMDDTHHMMSS.txt` を処理フォルダに出力します。
- 処理は直列実行で、ストリーミング I/O を使いファイル全体を一度にメモリへ読み込みません。

## パス長に関する注意

- Windows の拡張長パスをサポートするため、内部で `\\?\\` プレフィックスを利用しています（ファイルの open/replace/unlink 操作時）。
- それでもパスが長すぎて失敗する場合は、Windows のロングパス（グループポリシーやレジストリ設定）を有効にする必要があるか確認してください。

## 終了コード

- `0`: エラーなしで正常終了。
- `1`: 1 つ以上のエラーが発生（詳細はサマリーログを参照）。

## 補足事項

- `copy /b` を利用してパーツを連結しますが、ワイルドカードは用いず明示的なファイル一覧で連結順を制御します。
- 最終出力は `<dest>\\<internal_path>\\<name>` に書き込まれ、一時ファイルは `<dest>\\.winbak_tmp` に格納されます。
- 処理完了時（エラーが発生していても）に `.winbak_tmp` 以下の空ディレクトリは下位から削除され、ルートが空になればルートも削除されます。

## 使用例

- 基本的なディレクトリ処理:
  `python winbak_extract.py --dir "D:\\Win7Backup"`

- Backup Set フォルダ（直下のサブフォルダそれぞれを処理）:
  `python winbak_extract.py --set "D:\\Win7BackupSet"`

- 明示的に ZIP ファイルを指定する例:
  `python winbak_extract.py --files "D:\\Win7Backup\\Backup files 1.zip" "D:\\Win7Backup\\Backup files 2.zip"`
