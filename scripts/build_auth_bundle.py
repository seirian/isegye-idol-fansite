#!/usr/bin/env python3
"""Build inactive, credential-free PHP runtime. No main build or remote changes."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'auth-bundle'
FILES=('Store.php','GoogleVerifier.php','Session.php','View.php','Gateway.php','style.css','account.css','client.js','google-client.js')
def main():
    vendor=ROOT/'auth/vendor'
    if not (vendor/'autoload.php').is_file():raise RuntimeError('Install pinned Composer dependencies first')
    if OUT.exists():shutil.rmtree(OUT)
    OUT.mkdir()
    for name in FILES:shutil.copyfile(ROOT/'auth'/name,OUT/name)
    shutil.copytree(vendor,OUT/'vendor')
    shutil.copyfile(ROOT/'review/isegye-group-hero.webp',OUT/'background.webp')
    (OUT/'.htaccess').write_text('Require all denied\n')
    entry='''<?php
// ISEGYE-GOOGLE-ACCESS-V1
// Installed only after configuration and routing checks; never authenticates a fixture user.
declare(strict_types=1);
umask(0077); ini_set('display_errors','0'); ini_set('log_errors','0');
$root=__DIR__;
try {
    $runtime=$root.'/.auth-runtime/RUNTIME_ID';
    require $runtime.'/vendor/autoload.php';
    foreach(['Store','GoogleVerifier','Session','View','Gateway'] as $file)require_once $runtime.'/'.$file.'.php';
    $config=json_decode(file_get_contents($root.'/.auth-private/config.json'),true,16,JSON_THROW_ON_ERROR);
    (new Isegye\\Access\\Gateway($root,$runtime,$config))->run();
} catch (Throwable $e) {
    http_response_code(503); header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: no-store'); header('X-Robots-Tag: noindex');
    echo '일시적으로 접속할 수 없습니다. 잠시 후 다시 시도해 주세요.';
}
'''
    (OUT/'access.php.template').write_text(entry)
    files={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file()}
    runtime='g'+hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
    (OUT/'manifest.json').write_text(json.dumps({'runtime':runtime,'files':files,'active':False,'personalDataIncluded':False},indent=2)+'\n')
    print(json.dumps({'runtime':runtime,'files':len(files),'active':False}))
if __name__=='__main__':main()
