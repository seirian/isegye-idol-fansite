<?php
// LOOPBACK TEST ONLY. Never added to the auth runtime or uploaded to production.
declare(strict_types=1);
if (PHP_SAPI !== 'cli-server' || !in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1','::1'], true)) { http_response_code(404); exit; }
umask(0077);
$runtime=__DIR__.'/../auth-bundle';
require $runtime.'/vendor/autoload.php';
foreach(['Store','GoogleVerifier','Session','View','Gateway'] as $file) require_once $runtime.'/'.$file.'.php';
$root=getenv('ISEGYE_FIXTURE_ROOT');
if (!$root || !is_dir($root)) exit(1);
$_SERVER['HTTP_HOST']='isegye-idol.kr'; $_SERVER['HTTPS']='on'; $_SERVER['SERVER_PORT']='443';
if (($_SERVER['HTTP_ORIGIN'] ?? '') === getenv('ISEGYE_FIXTURE_ORIGIN')) $_SERVER['HTTP_ORIGIN']='https://isegye-idol.kr';
try { (new Isegye\Access\Gateway($root,$runtime,json_decode(file_get_contents($root.'/.auth-private/config.json'),true)))->run(); }
catch(Throwable) { http_response_code(503); header('Cache-Control: no-store'); echo 'Temporarily unavailable'; }
