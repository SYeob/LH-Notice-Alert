"""LH rental notice monitor CLI. Requires Python 3.11+."""
import argparse
import json
import logging
import sys
from contextlib import ExitStack


def main(argv=None):
    if sys.version_info < (3, 11):
        print('Python 3.11 이상이 필요합니다.', file=sys.stderr)
        return 2
    from config import Config, ROOT
    from filelock import FileLock, Timeout
    from src.crawler import Crawler
    from src.database import Database
    from src.detector import Monitor
    from src.logger import setup_logging
    from src.scheduler import run_forever
    from src.telegram import Telegram, TelegramError

    parser = argparse.ArgumentParser(description='LH 경기도 신규 임대주택 공고 알림')
    group = parser.add_mutually_exclusive_group()
    for flag, help_text in [('once', '1회 조회 및 발송'), ('init', '기존 DB를 보호하며 최초 무알림 초기화'),
                            ('test-telegram', '텔레그램 테스트 메시지'), ('status', 'DB 상태 조회'),
                            ('dry-run', '1회 조회/비교만 수행, DB 상태 및 발송 불변')]:
        group.add_argument('--' + flag, action='store_true', help=help_text)
    args = parser.parse_args(argv)
    try:
        config = Config.load()
        if not (args.status or args.dry_run or args.init):
            config.require_telegram()
        setup_logging(ROOT, config.log_level, (config.telegram_bot_token, config.telegram_chat_id))
        log = logging.getLogger('lh_monitor')
        with ExitStack() as stack:
            # Status/dry-run open SQLite in read-only mode, including no file creation.
            if not args.status:
                config.db_path.parent.mkdir(parents=True, exist_ok=True)
                stack.enter_context(FileLock(str(config.db_path) + '.lock', timeout=0))
            db = Database(config.db_path, read_only=args.status or args.dry_run)
            stack.callback(db.close)
            if args.status:
                print(json.dumps(db.summary(), ensure_ascii=False, indent=2))
                return 0
            log.info('시작: 모드=%s', next((k for k, v in vars(args).items() if v), 'monitor'))
            try:
                telegram = None
                if not (args.dry_run or args.init):
                    telegram = Telegram(config)
                    stack.callback(telegram.close)
                if args.test_telegram:
                    message_id = telegram.send('[LH] 임대주택 공고 모니터 테스트 알림입니다.')
                    log.info('테스트 발송 성공 message_id=%s', message_id)
                    return 0
                crawler = Crawler(config)
                stack.callback(crawler.close)
                monitor = Monitor(config, db, crawler, telegram)
                if args.once or args.init or args.dry_run:
                    return 0 if monitor.run_once(dry_run=args.dry_run, init=args.init) else 1
                run_forever(monitor, config.daily_check_time)
                return 0
            finally:
                log.info('종료')
    except Timeout:
        print('동일 DB를 사용하는 프로세스가 이미 실행 중입니다.', file=sys.stderr)
        return 2
    except (ValueError, TelegramError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        # No traceback: HTTP request objects may contain credentials.
        print(f'실행 오류 [{type(exc).__name__}]: 상태를 보존했습니다. 로그와 DB 경로를 확인하세요.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
