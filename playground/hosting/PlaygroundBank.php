<?php
declare(strict_types=1);
namespace Isegye\Access;
/** Called only after the existing account and maintenance gate. No account writes. */
final class PlaygroundBank
{
    public static function serve(string $root, string $release): void
    {
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: private, no-store, max-age=0');
        $file=$root.'/.playground-bank/current.json';
        try {
            $marker=$root.'/.playground-bank/.owner';
            if (is_link($marker)||!is_file($marker)||realpath($marker)!==$marker||file_get_contents($marker)!=="isegye-playground-bank:v1\n") throw new \RuntimeException('No bank');
            if (is_link($file)||!is_file($file)||realpath($file)!==$file||filesize($file)>5000000) throw new \RuntimeException('Bank bounds');
            $raw=file_get_contents($file);$d=json_decode($raw,true,32,JSON_THROW_ON_ERROR);
            $seed=json_decode(file_get_contents($release.'/src/playground-seed.json'),true,32,JSON_THROW_ON_ERROR);
            if (($d['schemaVersion']??0)!==1||($d['feed']??'')!=='playground'||($d['baseVersion']??'')!==($seed['version']??null)||!is_array($d['catalog']['questions']??null)) throw new \RuntimeException('Bank schema');
            if (($_SERVER['REQUEST_METHOD']??'GET')!=='HEAD') echo $raw;
            return;
        } catch (\Throwable) {
            // A verified compiled seed always works if a collector or feed is unavailable.
            $file=$release.'/src/playground-seed.json';
            if (is_file($file)&&!is_link($file)&&realpath($file)===$file&&filesize($file)<=5000000) {
                try {
                    $seed=json_decode(file_get_contents($file),true,32,JSON_THROW_ON_ERROR);
                    $data=['schemaVersion'=>1,'feed'=>'playground','baseVersion'=>$seed['version'],'generatedAt'=>gmdate('c',filemtime($file)),'catalog'=>$seed,'fallback'=>true];
                    if (($_SERVER['REQUEST_METHOD']??'GET')!=='HEAD') echo json_encode($data,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
                    return;
                } catch (\Throwable) {}
            }
            http_response_code(503); if (($_SERVER['REQUEST_METHOD']??'GET')!=='HEAD') echo '{"error":"question_bank_unavailable"}';
        }
    }
}
