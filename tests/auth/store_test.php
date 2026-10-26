<?php
declare(strict_types=1);
require __DIR__ . '/../../auth/Store.php';
require __DIR__ . '/../../auth/Gateway.php';
require __DIR__ . '/../../auth/View.php';
require __DIR__ . '/../../auth/Session.php';
use Isegye\Access\Store;
use Isegye\Access\Gateway;
use Isegye\Access\View;

umask(0077);
$dir = sys_get_temp_dir() . '/isegye-store-test-' . bin2hex(random_bytes(8)); mkdir($dir,0700);
$key = random_bytes(32); $adminEmail = 'owner.fixture@gmail.com';
file_put_contents($dir.'/accounts.json', json_encode(['schema'=>1,'administrator'=>null,'accounts'=>new stdClass()])); chmod($dir.'/accounts.json',0600);
file_put_contents($dir.'/accounts.lock',''); chmod($dir.'/accounts.lock',0600);
$store = new Store($dir,$key,Store::emailDigest($adminEmail,$key));
$checks = [];
function check(string $name,bool $ok): void { global $checks; $checks[]=['name'=>$name,'passed'=>$ok]; if (!$ok) throw new RuntimeException($name); }
function rejects(string $name, callable $fn): void { try { $fn(); } catch(Throwable) { check($name,true);return; } check($name,false); }
try {
    check('site public before any account', $store->access(null)['allowed'] && !$store->access(null)['maintenance']);
    $member=$store->registerVerified('subject-member','member.fixture@gmail.com');
    check('first visitor is only a member', $member['role']==='member' && !$member['activated']);
    check('member signup does not enable construction', $store->access(null)['allowed']);
    check('repeated Google login does not duplicate account', $store->registerVerified('subject-member','member.fixture@gmail.com')['key']===$member['key']);
    foreach(['owner.fixture@gmail.com.attacker.test','owner.fixture+attacker@gmail.com','ownerfixture@gmail.com'] as $i=>$email) {
        check('admin email must match exactly '.$i,$store->registerVerified('attacker-'.$i,$email)['role']==='member');
    }
    check('lookalike email cannot close site', !$store->access(null)['maintenance']);
    $admin=$store->registerVerified('subject-owner',$adminEmail);
    check('only designated verified Google account is admin', $admin['role']==='admin' && $admin['activated']);
    check('registration atomically enables maintenance', $store->access(null)['maintenance']);
    check('anonymous denied after admin signup', !$store->access(null)['allowed']);
    check('existing member denied after admin signup', !$store->access($member['key'])['allowed']);
    check('unknown forged member id denied', !$store->access(str_repeat('a',64))['allowed']);
    check('administrator alone allowed', $store->access($admin['key'])['allowed']);
    check('admin state persists after reopening', (new Store($dir,$key,Store::emailDigest($adminEmail,$key)))->access(null)['maintenance']);
    check('admin not rebound to another Google subject', $store->registerVerified('different-subject',$adminEmail)['role']==='member');
    check('admin logout does not reopen site', !$store->access(null)['allowed']);
    $state=json_decode(file_get_contents($dir.'/accounts.json'),true);
    check('accounts contain only keyed identifier and role', count(array_filter($state['accounts'],fn($x)=>is_string($x)))===count($state['accounts']));
    $raw=file_get_contents($dir.'/accounts.json');
    foreach(['@gmail.com','subject-owner','subject-member','email','picture','name','access_token','credential'] as $secret) check('no raw identity field '.$secret,!str_contains($raw,$secret));
    check('private account permissions retained',(fileperms($dir.'/accounts.json') & 0777)===0600);
    check('no write temporary left',glob($dir.'/accounts.tmp-*')===[]);
    rejects('invalid subject refused',fn()=>$store->registerVerified('../secret','a@b.test'));
    $otherKey=random_bytes(32);
    check('different site secret gives unlinkable account key',(new Store($dir,$otherKey,Store::emailDigest($adminEmail,$otherKey)))->accountKey('subject-owner')!==$admin['key']);
    foreach(['/../secret','/%2e%2e/secret','/%252e%252e/secret','//evil.test','/assets/a%00.jpg','/assets/%5csecret','/a/./b','/a%0db'] as $bad) rejects('path rejected '.$bad,fn()=>Gateway::path($bad));
    check('query is not used as filesystem path',Gateway::path('/src/app.js?path=../../secret')==='/src/app.js');
    check('maintenance includes requested exact wording',str_contains(str_replace('<br>','',View::maintenance()),'현재 사이트는 공사중입니다.') || str_contains(View::maintenance(),'현재 사이트는 공사중입니다.'));
    check('maintenance never exposes designated account',!str_contains(View::maintenance(),'seirian'));
    $saved=$raw; file_put_contents($dir.'/accounts.json','broken');
    rejects('corrupt data does not reopen site',fn()=>$store->access(null)); file_put_contents($dir.'/accounts.json',$saved);
    unlink($dir.'/accounts.json'); rejects('missing data does not recreate public state',fn()=>$store->access(null)); file_put_contents($dir.'/accounts.json',$saved);chmod($dir.'/accounts.json',0600);
    // Many concurrent processes must not lose registrations or reset owner binding.
    if (function_exists('pcntl_fork')) {
        $children=[];
        for($i=0;$i<12;$i++) { $pid=pcntl_fork(); if($pid===0) { $store->registerVerified('parallel-'.$i,'parallel'.$i.'@example.test');exit(0); } $children[]=$pid; }
        foreach($children as $pid){pcntl_waitpid($pid,$status);check('concurrent registration exits successfully',pcntl_wexitstatus($status)===0);}
        $s=json_decode(file_get_contents($dir.'/accounts.json'),true);
        check('concurrent registrations not lost',count($s['accounts'])===count($state['accounts'])+12);
        check('concurrent registration cannot reset maintenance',$s['administrator']===$admin['key']);
    }
    @mkdir(__DIR__.'/../../test-results/auth',0755,true);
    $report=['scope'=>'isolated synthetic accounts only; no Google or hosting users','passed'=>count($checks),'total'=>count($checks),'checks'=>$checks];
    file_put_contents(__DIR__.'/../../test-results/auth/store.json',json_encode($report,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));
    echo json_encode(['passed'=>count($checks),'total'=>count($checks)])."\n";
} finally { foreach(glob($dir.'/*') as $p)unlink($p);rmdir($dir); }
