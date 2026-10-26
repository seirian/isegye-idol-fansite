<?php
declare(strict_types=1);
namespace Isegye\Access;
final class View
{
    public static function e(string $text): string { return htmlspecialchars($text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
    public static function page(string $title, string $content, string $extra = ''): string
    {
        return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            . '<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="strict-origin-when-cross-origin">'
            . '<title>' . self::e($title) . ' · ISEGYE!</title><link rel="stylesheet" href="/auth/style.css">' . $extra
            . '</head><body class="access-page"><div class="access-backdrop" aria-hidden="true"></div>'
            . '<header class="access-brand"><a href="/">ISEGYE<span>!</span></a><span>이세계아이돌 비공식 팬사이트</span></header>'
            . '<main class="access-main">' . $content . '</main><footer class="access-footer">비공식 팬사이트 · <a href="/auth/privacy">개인정보 안내</a></footer></body></html>';
    }
    public static function maintenance(bool $signedIn = false): string
    {
        return self::page('공사중', '<section class="access-card maintenance"><div class="access-mark" aria-hidden="true">✦</div>'
            . '<p class="access-kicker">조금 더 좋은 모습으로 만나요</p><h1>현재 사이트는 <br>공사중입니다.</h1>'
            . '<p class="access-description">이세계아이돌의 소식을 더 편하게 만날 수 있도록<br class="wide-only"> 사이트를 준비하고 있어요.</p>'
            . '<div class="access-divider" aria-hidden="true"><span></span>✦<span></span></div>'
            . '<a class="access-small-link" href="/auth/login">' . ($signedIn ? '로그인 상태 · 계정 관리' : 'Google 로그인') . '</a></section>');
    }
    public static function login(string $clientId, string $nonce, string $csrf): string
    {
        $attrs = ' data-client-id="' . self::e($clientId) . '" data-nonce="' . self::e($nonce) . '" data-csrf="' . self::e($csrf) . '"';
        return self::page('Google 로그인', '<section class="access-card"><p class="access-kicker">다시 만나서 반가워요</p><h1>Google 로그인</h1>'
            . '<p class="access-description">가입 양식 없이 Google 계정으로 시작하세요.<br>처음 로그인하면 회원으로 자동 등록됩니다.</p>'
            . '<div id="google-signin"' . $attrs . '><p class="access-description" id="signin-loading">로그인 버튼을 불러오는 중입니다.</p><div id="google-button"></div></div>'
            . '<p id="signin-error" class="access-error" role="alert" hidden></p>'
            . '<p class="access-note">이름·이메일·프로필 사진은 저장하지 않습니다.<br>로그인 확인용 식별값과 권한만 보관합니다.</p>'
            . '<a class="access-small-link" href="/">사이트로 돌아가기</a></section>',
            '<script src="https://accounts.google.com/gsi/client" defer></script><script src="/auth/google-client.js" defer></script>');
    }
    public static function account(string $role, string $csrf): string
    {
        return self::page('로그인 상태', '<section class="access-card"><p class="access-kicker">로그인되었습니다</p><h1>'
            . ($role === 'admin' ? '관리자 계정' : '일반회원 계정') . '</h1><p class="access-description">Google 로그인으로 인증된 계정입니다.</p>'
            . '<a class="access-button" href="/">사이트로 돌아가기</a><form method="post" action="/auth/logout">'
            . '<input type="hidden" name="csrf" value="' . self::e($csrf) . '"><button class="access-secondary" type="submit">로그아웃</button></form></section>');
    }
    public static function privacy(): string
    {
        return self::page('개인정보 안내', '<article class="access-card access-privacy"><h1>로그인 정보 안내</h1>'
            . '<h2>저장하는 최소 정보</h2><p>Google 계정의 고유값을 사이트 전용 비밀키로 변환한 로그인 식별값과 회원 권한을 보관합니다. '
            . '이 값은 계정을 다시 알아보는 데 필요하므로 완전히 익명인 정보는 아닙니다.</p>'
            . '<h2>저장하지 않는 정보</h2><p>이름, 이메일 주소, 프로필 사진, 원본 Google 계정 고유값, Google 인증 토큰은 회원 저장소에 남기지 않습니다. '
            . 'Google이 확인한 이메일은 관리자 계정 판정에 잠시 사용한 뒤 버립니다. 사이트 자체 비밀번호는 만들지 않습니다.</p>'
            . '<h2>로그인 유지</h2><p>로그인 상태와 요청 위조 방지를 위한 필수 쿠키 및 임시 서버 세션을 사용합니다. '
            . '세션에는 변환된 식별값, 만료 확인 시각과 요청 검증용 값만 저장하며 최대 12시간, 활동이 없으면 30분 후 만료됩니다.</p>'
            . '<h2>보관과 정정</h2><p>회원 식별값과 권한은 회원 상태 유지에 사용합니다. 삭제·정정 요청은 사이트의 권리·정정 창구로 전달할 수 있습니다. '
            . '관리자 기록의 삭제는 사이트 공개 상태를 자동으로 되돌리지 않도록 별도로 검토합니다.</p>'
            . '<h2>서비스 제공자의 처리</h2><p>Google 로그인과 호스팅 제공자의 접속 기록에는 각 제공자의 처리방침이 적용됩니다. '
            . '애플리케이션은 이메일·토큰·IP 주소·브라우저 정보의 별도 회원 로그를 생성하지 않습니다.</p>'
            . '<a class="access-small-link" href="/">돌아가기</a></article>');
    }
}
