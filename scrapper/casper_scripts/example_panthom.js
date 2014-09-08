
phantom.casperPath = '/usr/local/Cellar/casperjs/1.0.3/libexec/';
phantom.injectJs('/usr/local/Cellar/casperjs/1.0.3/libexec/bin/bootstrap.js');


var webPage = require('webpage');
var page = webPage.create();

page.open('https://twitter.com', function (status) {
  var content = page.content;
  console.log('Content: ' + content);
  phantom.exit();
});