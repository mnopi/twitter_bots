var casper = require('casper').create({
    viewportSize: {width: 1024, height: 768},
    verbose: true,
    logLevel: "info",
    pageSettings: {
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.97 Safari/537.11"
    }
});


casper.start();

//casper.wait(100000, function() {
//    this.echo("I've waited for a second.");
//});

casper.thenOpen('http://whatismyip.com', function(){
    this.capture('/Users/rmaja/myip.png');
});

casper.thenOpen('http://whatsmyuseragent.com', function(){
    this.capture('/Users/rmaja/myuseragent.png');
});



casper.run();