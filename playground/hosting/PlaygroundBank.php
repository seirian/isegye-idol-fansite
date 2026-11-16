<?php
declare(strict_types=1);
namespace Isegye\Access;
/** Called only after the existing account and maintenance gate. No account writes. */
final class PlaygroundBank
{
    private static function canonical(mixed $v): string
    {
        $sort=function(mixed $x) use (&$sort): mixed {
            if (!is_array($x)) return $x;
            if (!array_is_list($x)) ksort($x,SORT_STRING);
            foreach ($x as $k=>$child) $x[$k]=$sort($child);
            return $x;
        };
        return json_encode($sort($v),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
    }
    /** Add reviewed seed facts to a still-valid previous daily snapshot in memory. */
    private static function expand(array $feed,array $seed): array
    {
        $catalog=$feed['catalog'];$ids=[];
        if (($catalog['version']??'')!==$seed['version'] ||
            self::canonical($catalog['tracks']??[])!==self::canonical($seed['tracks']) ||
            self::canonical($catalog['categories']??[])!==self::canonical($seed['categories']) ||
            !is_array($catalog['sources']??null)) throw new \RuntimeException('Bank facts');
        foreach ($catalog['questions'] as $q) {
            $id=$q['id']??'';
            if (!is_string($id)||!preg_match('/\A[a-z0-9-]{1,60}\z/D',$id)||isset($ids[$id])) throw new \RuntimeException('Question identity');
            $ids[$id]=$q;
        }
        $added=0;
        foreach ($seed['questions'] as $q) {
            if (isset($ids[$q['id']])) {
                if (self::canonical($ids[$q['id']])!==self::canonical($q)) throw new \RuntimeException('Reviewed answer changed');
            } else {$catalog['questions'][]=$q;$added++;}
        }
        foreach ($seed['sources'] as $id=>$source) {
            if (isset($catalog['sources'][$id]) && self::canonical($catalog['sources'][$id])!==self::canonical($source)) throw new \RuntimeException('Reviewed evidence changed');
            $catalog['sources'][$id]=$source;
        }
        if (count($catalog['questions'])>1000) throw new \RuntimeException('Question bound');
        $catalog['categories']=$seed['categories'];
        $feed['catalog']=$catalog;$feed['seedExpansionApplied']=$added;
        $feed['sha256']=hash('sha256',self::canonical($catalog)."\n");
        return $feed;
    }
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
            if (!is_string($d['sha256']??null)||!hash_equals($d['sha256'],hash('sha256',self::canonical($d['catalog'])."\n"))) throw new \RuntimeException('Bank integrity');
            $merged=self::expand($d,$seed);
            // Preserve exact stored bytes once the daily publisher has migrated the bank.
            $out=$merged['seedExpansionApplied']===0?$raw:json_encode($merged,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
            if (($_SERVER['REQUEST_METHOD']??'GET')!=='HEAD') echo $out;
            return;
        } catch (\Throwable) {
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
