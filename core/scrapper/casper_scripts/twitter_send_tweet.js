var casper = require('casper').create({
    viewportSize: {width: 1024, height: 768},
    //verbose: true,
    //logLevel: "debug"

    pageSettings: {
        loadImages: false
    //    userAgent: this.cli.get('useragent')
    }
});

var mouse = require("mouse").create(casper);

var utils = require('utils');

var output = {
    errors: [],
    not_found_el_css: null
};

var capture_index = 0,
    cookies_file = casper.cli.get('cookies-file2');

function getRandomIntFromRange(min, max) {
  return Math.round(Math.random() * (max - min)) + min;
}

function capture(name, force_take){
    take_screenshots = Boolean(casper.cli.get('take-screenshots'));
    force_take = force_take || false;
    if (take_screenshots || force_take)
    {
        capture_index++;
        casper.capture(casper.cli.get('screenshots') + capture_index + '_' + name + '.png');
    }
}

function click(el){
    check_el_css(el);
    casper.mouse.move(el);
    casper.mouse.click(el);
}

function check_el_css(el)
{
    if (!casper.visible(el)){
        output.errors.not_found_el_css = el;
        exit();
    }
}

function write_tweet_delayed_keys()
{
    var tweet_msg = casper.cli.get('tweetmsg');
    // se escribe el tweet
    for (var i in tweet_msg) {
        var current_letter = tweet_msg[i],
            delay = getRandomIntFromRange(200, 600); // entre 200 y 600 ms se pulsan teclas
        casper.wait(
            delay,
            (function (i, current_letter) {
                return function () {
                    casper.sendKeys(tweet_dialog_css, current_letter, {keepFocus: true});
                    //casper.echo('Sent: ' + current_letter);
                };
            })(i, current_letter)
        );
    }
}

function write_tweet()
{
    var tweet_msg = casper.cli.get('tweetmsg');
    casper.sendKeys(tweet_dialog_css, tweet_msg, {keepFocus: true});
}

function print_output()
{
    casper.echo(JSON.stringify(output));
}

function save_cookies()
{
    var fs = require('fs');
    var cookies = JSON.stringify(casper.cookies);
    fs.write(cookies_file, cookies, 644);
}

function restore_cookies()
{
    var fs = require('fs');
    var data = fs.read(cookies_file);
    casper.cookies = JSON.parse(data);
}

function remove_old_cookies_file()
{
    var fs = require('fs');
    fs.remove(casper.cli.get('old_cookies'));
}

function exit()
{
    print_output();
    casper.exit();
}

casper.start();

//casper.echo(casper.cli.get('useragent'));
//casper.echo(casper.cli.get('pageload-timeout'));

casper.userAgent(casper.cli.get('useragent'));
casper.page.customHeaders = {'Accept-Language': 'en'};
casper.options.waitTimeout = parseInt(casper.cli.get('pageload-timeout')) * 1000;

casper.onError = function(){
    capture('casperjs_error');
    output.errors.push('casperjs_error');
    exit();
};

//pageloadtimeout = parseInt(casper.cli.get('pageload-timeout')) * 1000;
//pageloadtimeout = 20;
//pageloadtimeout_error = false;
//casper.waitFor(function check() {
//    casper.thenOpen("https://twitter.com", function() {
//        //+++ casper will wait until this returns true to move forward.
//        //+++ The default timeout is set to 5000ms
//        this.echo('meeeee');
//        this.evaluate(function() {
//            //checks for element exist
//            //tweet_btn_exists = document.getElementById('#global-new-tweet-button');
//            //login_btn_exists = document.getElementById('#signin-email');
//            //if (tweet_btn_exists || login_btn_exists) {
//            //    // console.log('Im loaded!');
//            //    return true;
//            //}
//            return true;
//        });
//    });
//}, function then() {    // step to execute when function check() is ok
//    //+++ executes ONLY after the 'casper.thenOpen' returns true.
//    //this.echo("THEN!", "GREEN_BAR");
//    this.echo('oook');
//
//}, function timeout() { // step to execute if check has failed
//    //+++ code for on timeout.  This is different than onStepTimeOut.
//    this.echo('timeout!');
//    this.exit();
//}, pageloadtimeout);// custom timeOut setting.

casper.thenOpen('https://twitter.com', function then(){
    //capture('hola');
    //this.echo(this.page.cookies);
});

casper.then(function () {

    // limpiamos lo que hubiera en localstorage
    this.evaluate(function () {
        localStorage.clear();
    }, {});

    if (!this.getHTML('body'))
    {
        capture('internet_connection_error');
        output.errors.push('internet_connection_error');
        exit();
    }
    else
    {
        capture('page_loaded');
    }
});

// hacemos click en botón de escribir nuevo tweet
var tweet_btn_css = '#global-new-tweet-button';
casper.waitUntilVisible(tweet_btn_css,
    function then() {
        click(tweet_btn_css);
    },
    function onTimeout() {
        capture('not_logged_in', true);
        output.errors.push('not_logged_in');
        exit();
    }
);

// escribimos el tweet, adjuntamos imagen si fuera necesario
var tweet_dialog_css = '#global-tweet-dialog-dialog div.tweet-content';
casper.waitUntilVisible(tweet_dialog_css,
    function then() {
        capture('tweet_dialog_loaded');

        casper.wait(getRandomIntFromRange(2000, 5000));
        write_tweet();
        casper.wait(getRandomIntFromRange(7000, 15000));

        img_path = casper.cli.get('tweetimg');
        if (img_path)
        {
            casper.wait(getRandomIntFromRange(3000, 5000));
            form_css = '#global-tweet-dialog-dialog > div.modal-content > div.modal-tweet-form-container > form';
            casper.fillSelectors(form_css, {
                'input[type="file"][name="media_empty"]': img_path
            }, false);
            //img_btn_css = '#global-tweet-dialog-dialog > div.modal-content > div.modal-tweet-form-container > form > div.toolbar.js-toolbar > div.tweet-box-extras > div.photo-selector > div > label > input';
            //casper.sendKeys(img_btn_css, img_path);
            casper.wait(getRandomIntFromRange(800, 2000));
        }
    }
);

// pulsamos el botón para enviarlo
casper.then(function(){
    casper.click('#global-tweet-dialog-dialog .tweet-button button');
});

// esperamos a ver si se envió bien o no
casper.wait(getRandomIntFromRange(5000, 10000),
    function then() {
        capture('clicked_send_tweet_btn');

        if (this.visible('#global-tweet-dialog-dialog'))
        {
            unknown_error = true;

            var msg_drawer = '#message-drawer .message-text',
                captcha_form = '#captcha-challenge-form',
                acc_blocked_card = '.PromptbirdPrompt-title';

            if (this.visible(captcha_form))
            {
                output.errors.push('captcha_required');
                capture('captcha_required', true);
                unknown_error = false;
            }
            else if (this.visible(msg_drawer))
            {
                msg_drawer_text = this.fetchText(msg_drawer).toLowerCase();
                if (msg_drawer_text.indexOf("already sent") >= 0) {
                    output.errors.push('tweet_already_sent');
                    capture('tweet_already_sent', true);
                    unknown_error = false;
                }
                else if (msg_drawer_text.indexOf("suspended") >= 0) {
                    output.errors.push('account_suspended');
                    capture('account_suspended', true);
                    unknown_error = false;
                }
                else if(this.visible(acc_blocked_card))
                {
                    acc_bloqued_card_text = this.fetchText(acc_blocked_card).toLowerCase();
                    if (acc_bloqued_card_text.indexOf("locked") >= 0) {
                        output.errors.push('account_locked');
                        capture('account_locked', true);
                        unknown_error = false;
                    }
                }
            }

            if (unknown_error)
            {
                output.errors.push('unknown_error');
                capture('unknown_error', true);
            }
        }
    }
);

casper.then(function () {
    this.echo(JSON.stringify(output));
});

casper.run();