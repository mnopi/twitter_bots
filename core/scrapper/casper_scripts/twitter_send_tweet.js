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
    casper.sendKeys(tweet_box_css, tweet_msg, {keepFocus: true});
    capture('tweet_written');
}

function do_tweet_writing()
{
    capture('tweet_box_loaded');

    casper.wait(getRandomIntFromRange(2000, 5000));
    write_tweet();
    casper.wait(getRandomIntFromRange(7000, 15000));

    img_path = casper.cli.get('tweetimg');
    if (img_path) {
        casper.wait(getRandomIntFromRange(3000, 5000));
        form_css = '#timeline > div.timeline-tweet-box > div > form';
        casper.fillSelectors(form_css, {
            'input[type="file"][name="media_empty"]': img_path
        }, false);
        //img_btn_css = '#global-tweet-dialog-dialog > div.modal-content > div.modal-tweet-form-container > form > div.toolbar.js-toolbar > div.tweet-box-extras > div.photo-selector > div > label > input';
        //casper.sendKeys(img_btn_css, img_path);
        casper.wait(getRandomIntFromRange(800, 2000));
    }
}

function print_output()
{
    casper.echo(JSON.stringify(output));
}

function exit()
{
    print_output();
    casper.exit();
}


//
// MAIN
//

var casper = require('casper').create({
    viewportSize: {width: 1024, height: 768},
    //verbose: true,
    //logLevel: "debug",

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
var unknown_error = true;


casper.start();

var capture_index = 0,
    pageload_timeout = parseInt(casper.cli.get('pageload-timeout'));
casper.userAgent(casper.cli.get('useragent'));
casper.page.customHeaders = {'Accept-Language': 'en'};
//casper.options.waitTimeout = parseInt(casper.cli.get('pageload-timeout')) * 1000;
//casper.options.waitTimeout = 10;

casper.onError = function(){
    capture('casperjs_error');
    output.errors.push('casperjs_error');
    exit();
};

casper.thenOpen('https://twitter.com', function then(){
    // vemos si carga a tiempo o no twitter
    this.waitForResource(this.getCurrentUrl(),
        function then() {
            //do stuff, page loaded
        }, function onTimeout() {
            //page load failed after x seconds
            output.errors.push('pageload_timeout_expired');
            exit();
        },
        pageload_timeout
    );
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


// hacemos click en la caja de texto para escribir nuevo tweet
var tweet_box_css = '#tweet-box-mini-home-profile';
casper.waitUntilVisible(tweet_box_css,
    function then() {
        this.wait(getRandomIntFromRange(2000, 5000));
        click(tweet_box_css);
    },
    function onTimeout() {
        if (casper.visible('#signin-email'))
        {
            capture('not_logged_in', true);
            output.errors.push('not_logged_in');
            exit();
        }
    }
);


// escribimos el tweet, adjuntamos imagen si fuera necesario
//var opened_tweet_box_css = '.timeline-tweet-box form.tweet-form .tweet-box-extras';
var send_tweet_btn_css = '.timeline-tweet-box form.tweet-form .tweet-button button';
casper.waitUntilVisible(send_tweet_btn_css,
    function then() {
        do_tweet_writing();
    },
    function onTimeout()
    {
        // si no ha dado tiempo a mostrar la cajita con el diálogo para escribir el tweet..
        capture('tweet_dialog_not_loaded1', true);
        casper.waitUntilVisible(send_tweet_btn_css,
            function then() {
                click(tweet_box_css);
                do_tweet_writing();
            },
            function onTimeout() {
                capture('tweet_dialog_not_loaded2', true);
                output.errors.push('tweet_dialog_not_loaded');
                exit();
            },
            5000
        );
    },
    5000
);


// pulsamos en botón de enviar el tweet ya escrito
casper.waitUntilVisible(send_tweet_btn_css,
    function then(){
        click(send_tweet_btn_css);
    }
);


// esperamos a ver si se envió bien o no
casper.wait(getRandomIntFromRange(5000, 10000),
    function then() {
        capture('clicked_send_tweet_btn');

        var msg_drawer = '#message-drawer .message-text',
            captcha_form = '#captcha-challenge-form',
            acc_blocked_card = '.PromptbirdPrompt-title';

        if (this.visible(msg_drawer) || this.visible(captcha_form))
        {
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
        }
        else
        {
            unknown_error = false;
        }
    }
);

casper.then(function () {
    if (unknown_error)
    {
        output.errors.push('unknown_error');
        capture('unknown_error', true);
    }
    this.echo(JSON.stringify(output));
});

casper.run();