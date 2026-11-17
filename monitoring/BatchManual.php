<?php
declare(strict_types=1);
namespace Isegye\Access;

/** Administrator POST -> bounded private outbox. GitHub tokens never reach PHP. */
final class BatchManual
{
    public const OWNER = "isegye-batch-manual:v1\n";
    public const BATCHES = ['albums','music','schedule','catalog','playground','history','production','watchdog'];
    private const ACTIVE = ['queued','checking','dispatching','accepted','unknown','running'];
    private static function send(int $code, array $data): void
    {
        http_response_code($code); header('Content-Type: application/json; charset=utf-8');
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'HEAD') echo json_encode($data, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
    }
    private static function headers(): void
    {
        header('Cache-Control: private, no-store, max-age=0'); header('Vary: Cookie');
        header('X-Robots-Tag: noindex, nofollow, noarchive'); header('X-Content-Type-Options: nosniff');
        header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'");
    }
    private static function folder(string $root): string
    {
        $folder=$root.'/.batch-monitoring/control';
        foreach ([$root,$root.'/.batch-monitoring',$folder] as $path) {
            if (is_link($path) || !is_dir($path) || realpath($path)!==$path) throw new \RuntimeException('unsafe_storage');
        }
        if (self::read($folder.'/.owner',128)!==self::OWNER || self::read($folder.'/.htaccess',128)!=="Require all denied\n") throw new \RuntimeException('unowned_storage');
        return $folder;
    }
    private static function read(string $file, int $limit): ?string
    {
        clearstatcache(true,$file);
        if (is_link($file)) throw new \RuntimeException('unsafe_file');
        if (!file_exists($file)) return null;
        if (!is_file($file) || realpath($file)!==$file || filesize($file)>$limit) throw new \RuntimeException('unsafe_file');
        $raw=file_get_contents($file,false,null,0,$limit+1);
        if (!is_string($raw) || strlen($raw)>$limit) throw new \RuntimeException('read_failed');
        return $raw;
    }
    private static function transaction(string $root, callable $fn): mixed
    {
        $folder=self::folder($root); $lockPath=$folder.'/queue.lock';
        self::read($lockPath,128); $lock=fopen($lockPath,'c+b');
        if (!$lock) throw new \RuntimeException('lock_unavailable');
        chmod($lockPath,0600);
        if (!flock($lock,LOCK_EX|LOCK_NB)) { fclose($lock); throw new \RuntimeException('queue_busy'); }
        $temp=null;
        try {
            $raw=self::read($folder.'/queue.json',524288);
            $db=$raw===null?['version'=>1,'heartbeat'=>null,'requests'=>[]]:json_decode($raw,true,16,JSON_THROW_ON_ERROR);
            if (($db['version']??null)!==1 || !is_array($db['requests']??null) || count($db['requests'])>256) throw new \RuntimeException('invalid_queue');
            foreach ($db['requests'] as $id=>&$r) {
                if (!preg_match('/\A[a-f0-9]{32}\z/D',(string)$id) || ($r['id']??null)!==$id || !in_array($r['batch']??null,self::BATCHES,true) || !is_int($r['at']??null)) throw new \RuntimeException('invalid_request');
                if ($r['state']==='queued' && time()-$r['at']>1200) { $r['state']='expired'; $r['reason']='queue_expired'; }
                if (in_array($r['state'],['checking','dispatching'],true) && time()-($r['changedAt']??$r['at'])>300) {
                    $r['state']=$r['state']==='checking'?'blocked':'unknown'; $r['reason']='worker_interrupted';
                }
            }
            unset($r);
            $result=$fn($db);
            // Only terminal records are pruned. Unresolved dispatches are never silently retried.
            foreach ($db['requests'] as $id=>$r) if (!in_array($r['state'],self::ACTIVE,true) && $r['at']<time()-604800) unset($db['requests'][$id]);
            while (count($db['requests'])>200) {
                $found=false;
                foreach ($db['requests'] as $id=>$r) if (!in_array($r['state'],self::ACTIVE,true)) { unset($db['requests'][$id]); $found=true; break; }
                if (!$found) break;
            }
            $json=json_encode($db,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR)."\n";
            if (strlen($json)>524288) throw new \RuntimeException('queue_capacity');
            $temp=$folder.'/q-'.bin2hex(random_bytes(12)).'.tmp'; $out=fopen($temp,'x+b');
            if (!$out) throw new \RuntimeException('write_failed');
            try { chmod($temp,0600); if (fwrite($out,$json)!==strlen($json) || !fflush($out)) throw new \RuntimeException('write_failed'); }
            finally { fclose($out); }
            if (!rename($temp,$folder.'/queue.json')) throw new \RuntimeException('write_failed');
            $temp=null; return $result;
        } finally { if ($temp!==null) @unlink($temp); flock($lock,LOCK_UN); fclose($lock); }
    }
    private static function payload(): array
    {
        if (explode(';',$_SERVER['CONTENT_TYPE']??'')[0]!=='application/json' || (int)($_SERVER['CONTENT_LENGTH']??0)>4096) throw new \InvalidArgumentException('invalid_payload');
        $raw=file_get_contents('php://input',false,null,0,4097);
        if (!is_string($raw) || strlen($raw)>4096) throw new \InvalidArgumentException('invalid_payload');
        $value=json_decode($raw,true,8,JSON_THROW_ON_ERROR);
        if (!is_array($value)) throw new \InvalidArgumentException('invalid_payload');
        return $value;
    }
    private static function publicRecord(array $r): array
    {
        return array_intersect_key($r,array_flip(['id','batch','at','changedAt','state','reason','runId','conclusion']));
    }
    public static function serve(string $root,string $path,array $access,string $origin): void
    {
        self::headers();
        if (($access['role']??null)!=='admin' || ($access['allowed']??false)!==true) { self::send(($access['role']??null)===null?401:403,['error'=>'administrator_required']); return; }
        if (in_array($path,['/ops/batches/manual.js','/ops/batches/manual.css'],true)) {
            if (!in_array($_SERVER['REQUEST_METHOD']??'', ['GET','HEAD'],true)) { self::send(405,['error'=>'method_not_allowed']); return; }
            header('Content-Type: '.($path==='/ops/batches/manual.js'?'text/javascript':'text/css').'; charset=utf-8');
            if ($_SERVER['REQUEST_METHOD']!=='HEAD') echo file_get_contents(__DIR__.'/'.basename($path));
            return;
        }
        try {
            if (($_SERVER['REQUEST_METHOD']??'')==='GET') {
                $data=self::transaction($root,static function (&$db) {
                    return ['version'=>1,'serverTime'=>time(),'heartbeat'=>$db['heartbeat'],
                        'requests'=>array_values(array_map([self::class,'publicRecord'],array_slice($db['requests'],-64,null,true)))];
                });
                $data['csrf']=Session::csrf(); self::send(200,$data); return;
            }
            if (($_SERVER['REQUEST_METHOD']??'')!=='POST') { header('Allow: GET, POST'); self::send(405,['error'=>'method_not_allowed']); return; }
            try { Session::requirePost($origin,$_SERVER['HTTP_X_CSRF_TOKEN']??null); }
            catch (\Throwable) { self::send(403,['error'=>'request_authenticity_rejected']); return; }
            $input=self::payload(); $account=Session::account();
            if ($account===null) { self::send(401,['error'=>'session_required']); return; }
            $result=self::submit($root,$input,$account);
            self::send($result['code'],$result);
        } catch (\InvalidArgumentException|\JsonException) { self::send(400,['error'=>'invalid_payload']); }
        catch (\Throwable) { self::send(503,['error'=>'manual_control_unavailable']); }
    }
    /** Caller must have just checked the live administrator session and CSRF. */
    public static function submit(string $root,array $input,string $account): array
    {
        if (count($input)!==4 || !isset($input['action'],$input['id'],$input['batch'],$input['confirm']) ||
            !in_array($input['action'],['enqueue','cancel','resolve'],true) || !is_string($input['id']) ||
            !preg_match('/\A[a-f0-9]{32}\z/D',$input['id']) || !in_array($input['batch'],self::BATCHES,true) ||
            $input['confirm']!==$input['batch'] || !preg_match('/\A[a-f0-9]{64}\z/D',$account)) throw new \InvalidArgumentException('invalid_payload');
        return self::transaction($root,static function (&$db) use ($input,$account) {
            $id=$input['id'];$batch=$input['batch'];$existing=$db['requests'][$id]??null;
            if ($input['action']!=='enqueue') {
                if (!$existing || $existing['batch']!==$batch) return ['code'=>404,'error'=>'request_not_found'];
                $states=$input['action']==='cancel'?['queued']:['unknown'];
                if (!in_array($existing['state'],$states,true)) return ['code'=>409,'error'=>'request_not_cancellable'];
                $db['requests'][$id]['state']=$input['action']==='cancel'?'cancelled':'resolved';
                $db['requests'][$id]['changedAt']=time();
                return ['code'=>200,'request'=>self::publicRecord($db['requests'][$id])];
            }
            if ($existing) {
                if ($existing['batch']!==$batch || $existing['actor']!==$account) return ['code'=>409,'error'=>'id_conflict'];
                return ['code'=>200,'request'=>self::publicRecord($existing)];
            }
            if (count($db['requests'])>=256) return ['code'=>503,'error'=>'queue_capacity'];
            $recent=0;
            foreach ($db['requests'] as $r) {
                if ($r['batch']!==$batch) continue;
                if (in_array($r['state'],self::ACTIVE,true)) return ['code'=>409,'error'=>'request_already_active'];
                if ($r['at']>time()-900) return ['code'=>429,'error'=>'cooldown'];
                if ($r['at']>time()-3600) $recent++;
            }
            if ($recent>=2) return ['code'=>429,'error'=>'hourly_limit'];
            if ($batch==='albums') {
                $h=(int)gmdate('G',time()+9*3600);
                if ($h>=1 && $h<7) return ['code'=>409,'error'=>'night_pause'];
            }
            $r=['id'=>$id,'batch'=>$batch,'actor'=>$account,'at'=>time(),'changedAt'=>time(),'state'=>'queued','reason'=>'awaiting_worker'];
            $db['requests'][$id]=$r; return ['code'=>202,'request'=>self::publicRecord($r)];
        });
    }
    /** Short-lived worker capability may ONLY claim/settle existing administrator requests. */
    public static function agent(string $root, callable $accessFor): void
    {
        self::headers();
        try {
            $token=$_SERVER['HTTP_X_ISEGYE_AGENT']??'';
            $folder=self::folder($root);$raw=self::read($folder.'/agent.json',2048);
            $grant=$raw===null?[]:json_decode($raw,true,8,JSON_THROW_ON_ERROR);
            if (($_SERVER['REQUEST_METHOD']??'')!=='POST' || !is_string($token) || !preg_match('/\A[a-f0-9]{64}\z/D',$token) ||
                !is_string($grant['tokenHash']??null) || !hash_equals($grant['tokenHash'],hash('sha256',$token)) ||
                !is_int($grant['expires']??null) || $grant['expires']<time() || $grant['expires']>time()+900 ||
                !preg_match('/\A[1-9][0-9]*\z/D',$grant['worker']??'')) { self::send(404,['error'=>'not_found']); return; }
            unset($token);
            $result=self::work($root,self::payload(),$grant['worker'],$accessFor);
            self::send(200,$result);
        } catch (\Throwable) { self::send(503,['error'=>'agent_unavailable']); }
    }
    public static function work(string $root,array $input,string $worker,callable $accessFor): array
    {
        return self::transaction($root,static function (&$db) use ($input,$worker,$accessFor) {
            $action=$input['action']??null;
            if ($action==='claim' && count($input)===1) {
                $db['heartbeat']=time();
                $pending=[];$tracking=[];
                foreach ($db['requests'] as &$r) {
                    if ($r['state']==='queued') {
                        $a=$accessFor($r['actor']);
                        if (($a['role']??null)!=='admin' || ($a['allowed']??false)!==true) { $r['state']='blocked';$r['reason']='administrator_revoked';continue; }
                        if (count($pending)>=8) continue;
                        $r['state']='checking';$r['worker']=$worker;$r['changedAt']=time();$pending[]=self::publicRecord($r);
                    } elseif (in_array($r['state'],['accepted','running'],true) && isset($r['runId'])) { $tracking[]=self::publicRecord($r); }
                }
                unset($r);return ['version'=>1,'pending'=>$pending,'tracking'=>$tracking];
            }
            $id=$input['id']??'';
            if (!is_string($id) || !isset($db['requests'][$id])) throw new \InvalidArgumentException('invalid_request');
            $r=&$db['requests'][$id];
            if ($action==='begin' && count($input)===2 && $r['state']==='checking' && ($r['worker']??'')===$worker) {
                $a=$accessFor($r['actor']);
                if (($a['role']??null)!=='admin' || ($a['allowed']??false)!==true || time()-$r['at']>1200) {
                    $r['state']='blocked';$r['reason']='authorization_or_expiry';return ['allowed'=>false];
                }
                $r['state']='dispatching';$r['changedAt']=time();return ['allowed'=>true];
            }
            if ($action==='settle' && count($input)<=5 && ($r['worker']??'')===$worker && in_array($r['state'],['checking','dispatching'],true)) {
                $state=$input['state']??'';$reason=$input['reason']??'';
                if (!in_array($state,['blocked','unknown','accepted'],true) || !in_array($reason,['paused','night_pause','existing_run','cooldown','hourly_limit','inspection_failed','accepted','dispatch_unconfirmed'],true)) throw new \InvalidArgumentException('invalid_result');
                if ($r['state']==='checking' && $state!=='blocked') throw new \InvalidArgumentException('not_dispatched');
                $run=$input['runId']??null;
                if ($state==='accepted' && (!is_int($run) || $run<=0)) throw new \InvalidArgumentException('invalid_run');
                $r['state']=$state;$r['reason']=$reason;$r['changedAt']=time();if ($run!==null) $r['runId']=$run;
                return ['ok'=>true];
            }
            if ($action==='status' && count($input)===4 && in_array($r['state'],['accepted','running'],true) && ($input['runId']??null)===($r['runId']??null)) {
                $conclusion=$input['conclusion']??'';
                if (!in_array($conclusion,['running','success','failure','cancelled','timed_out','skipped','action_required','neutral','startup_failure','stale'],true)) throw new \InvalidArgumentException('invalid_status');
                $r['state']=$conclusion==='running'?'running':'completed';$r['conclusion']=$conclusion;$r['changedAt']=time();return ['ok'=>true];
            }
            throw new \InvalidArgumentException('invalid_transition');
        });
    }
}
