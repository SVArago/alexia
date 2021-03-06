/*
 * Juliana by Cas Ebbers <cjaebbers@gmail.com>
 * Front-end application for bar personnel, in Abscint Bars
 * supporting Alexia
 */

State = {
    SALES: 0,
    PAYING: 1,
    ERROR: 2,
    CHECK: 3,
    MESSAGE: 4,
    UNDERAGE: 5,

    current: this.SALES,
    isLoading: false,

    toggleTo: function (newState, argument) {
        this.clearLoading();
        switch (newState) {
            case this.SALES:
                console.log('Changing to SALES...');
                this.current = this.SALES;
                this._hideAllScreens();

                clearInterval(Receipt.counterInterval);
                $('#cashier-screen').show();
                break;
            case this.CHECK:
                console.log('Changing to CHECK...');
                this.current = this.CHECK;
                break;
            case this.PAYING:
                console.log('Changing to PAYING...');
                this.current = this.PAYING;
                this._hideAllScreens();

                $('#rfid-screen').show();
                break;
            case this.ERROR:
                console.log('Changing to ERROR...');
                this.current = this.ERROR;
                this._hideAllScreens();

                $('#current-error').html(argument);
                $('#error-screen').show();
                break;
            case this.MESSAGE:
                console.log('Changing to MESSAGE...');
                this.current = this.MESSAGE;
                this._hideAllScreens();

                $('#current-message').html(argument);
                $('#message-screen').show();
                break;
            case this.UNDERAGE:
                console.log('Changing to UNDERAGE...');
                this.current = this.UNDERAGE;
                this._hideAllScreens();

                $('#underage-current').html(argument);
                $('#underage-screen').show();
            default:
                console.log('Error: switching to unknown state');
                break;
        }
    },

    setLoading: function () {
        this.isLoading = true;
    },
    clearLoading: function () {
        this.isLoading = false;
    },

    _hideAllScreens: function () {
        $('#rfid-screen').hide();
        $('#cashier-screen').hide();
        $('#error-screen').hide();
        $('#message-screen').hide();
        $('#underage-screen').hide();
    }
};

/*
 * NFC SCAN
 */
Scanner = {
    init: function () {
        var scanner = this;
        var socket;

        if (Settings.websocket_protocol != null) {
            socket = new WebSocket(Settings.websocket_url, Settings.websocket_protocol);
        } else {
            socket = new WebSocket(Settings.websocket_url);
        }

        socket.onopen = function (event) {
            console.log('Connected with websocket!');
        };

        socket.onerror = function (event) {
            console.log('Failed to connect with websocket, warning user.');
            alert('Verbinden met NFC-reader mislukt.');
        };

        socket.onmessage = function (event) {
            var rfid = JSON.parse(event.data);
            scanner.action(rfid);
        };
    },
    action: function (rfid) {
        if (State.isLoading)
            return;

        if (State.current === State.SALES) {
            if (Receipt.receipt.length > 0) {
                Receipt.pay(rfid);
            } else {
                console.log('Info: receipt empty');
                Display.set('Please select products!');
            }
        } else if (State.current === State.CHECK) {
            console.log('Requesting check');
            User.check(rfid);
        } else {
            console.log('Error: not on SALES or CHECK screen');
        }
    }
};

/*
 * DISPLAY - upper status line
 */
Display = {
    set: function (text) {
        $('#display').html(text);
    },
    flash: function () {
        $('#display').effect('shake').effect('highlight', {color: '#fcc'});
    }
};

/*
 * RECEIPT - right panel
 */
Receipt = {
    receipt: [],
    counterInterval: null,
    payData: null,
    add: function (product, quantity) {
        if (State.current !== State.SALES) {
            console.log('Error: not on SALES screen');
            Display.flash();
            return;
        }

        // Try to update the quantity of an old receipt entry if possible, else
        // add product to the receipt
        var foundProduct = false;
        for (var i in this.receipt) {
            if (this.receipt[i].product == product) {
                this.receipt[i].amount += quantity;
                this.receipt[i].price += quantity * Settings.products[product].price;
                foundProduct = true;
                break;
            }
        }

        if (!foundProduct)
            this.receipt.push({
                'product': product,
                'amount': quantity,
                'price': quantity * Settings.products[product].price
            });

        this.updateShownReceipt(product);
        Display.set('OK');
    },
    remove: function (index) {
        this.receipt.splice(index, 1);
        this.updateShownReceipt();
    },
    clear: function () {
        this.receipt = [];
        this.updateShownReceipt();
    },
    getTotal: function () {
        var sum = 0;
        for (var i in this.receipt) {
            if (this.receipt[i] === undefined)
                continue;

            sum += this.receipt[i].price;
        }

        return (sum / 100).toFixed(2);
    },
    updateShownReceipt: function(flashProduct) {
        $('#receipt-table').empty();
        for (var i in this.receipt) {
            if (this.receipt[i]===undefined)
                continue;

            var product = this.receipt[i].product;
            var quantity = this.receipt[i].amount;
            var price = (this.receipt[i].price / 100).toFixed(2);
            var desc = Settings.products[product].name;
            if (quantity !== 1)
                desc += ' &times; ' + quantity;

            var doFlash = (flashProduct!==undefined && flashProduct==product)?' class="flash"':'';
            $('#receipt-table').append('<tr' + doFlash + ' data-pid="' + i + '"><td width="75%"><a onclick="Receipt.remove($(this).data(\'pid\'));" class="btn btn-danger command" href="#" data-pid="' + i + '">X</a><span>' + desc + '</span></td><td>€' + price + '</td></tr>');
        }

        $('#receipt-total').find('input').val('€ ' + this.getTotal());
    },
    buildPaymentReceipt: function (user) {
        var receiptHTML = '';
        for (var i = 0; i < Receipt.receipt.length; i++) {
            receiptHTML += '<tr>';
            receiptHTML += '<td>' + Settings.products[this.receipt[i].product].name + '</td>';
            receiptHTML += '<td>' + this.receipt[i].amount + ' &times;</td>';
            receiptHTML += '<td>&euro;' + (this.receipt[i].price / 100).toFixed(2) + '</td>';
            receiptHTML += '</tr>';
        }

        receiptHTML += '<tr class="active"><td><strong>Totaal:</strong></td><td></td><td><strong>&euro;' + this.getTotal() + '</strong></td></tr>';

        $('#payment-receipt').html(receiptHTML);
        $('#payment-name').text(user.first_name);
    },
    pay: function (rfid) {
        console.log('Card scanned, retrieving data');
        State.setLoading();
        User.retrieveData(rfid, function (result) {
            Receipt.continuePay(result, rfid);
        });
    },
    continuePay: function (userData, rfid) {
        console.log('continuePay was called');
        if (!userData) {
            State.toggleTo(State.ERROR, 'RFID card retrieval failed');
        } else if (userData.error) {
            State.toggleTo(State.ERROR, 'Error authenticating: ' + userData.error.message);
        } else {
            console.log('Userdata received correctly.');
            Receipt.payForUser(userData.result.user, rfid);
        }
    },
    payForUser: function (user, rfid) {
        if (Receipt.receipt.length == 0) {
            console.log('Info: receipt empty');
            Display.set('Please select products!');
            return;
        }

        if (!user.alcohol_permitted) {
            for (var i = 0; i < Receipt.receipt.length; i++) {
                if (Settings.products[this.receipt[i].product].alcohol) {
                    // User is underage and tries to buy alcohol. Deny this sale.
                    State.toggleTo(State.UNDERAGE, user.first_name + ' ' + user.last_name);
                    return;
                }
            }
        }

        console.log('Starting pay countdown');
        Receipt.buildPaymentReceipt(user);
        if (State.current != State.PAYING)
            State.toggleTo(State.PAYING);

        Receipt.payData = {
            event_id: Settings.event_id,
            user_id: user.id,
            purchases: Receipt.receipt,
            rfid_data: rfid
        };

        var countdown = Settings.countdown - 1;
        $('#payment-countdown').text(countdown + 1);
        Receipt.counterInterval = setInterval(function () {
            $('#payment-countdown').text(countdown);
            if (countdown === 0) {
                Receipt.payNow();
            }
            countdown--;
        }, 1000);
    },
    payNow: function () {
        if (State.isLoading)
            return;
        State.setLoading();

        console.log('Processing payment now.');
        var rpcRequest = {
            jsonrpc: '2.0',
            method: 'juliana.order.save',
            params: Receipt.payData,
            id: 1
        };

        clearInterval(Receipt.counterInterval);

        IAjax.request(rpcRequest, function (result) {
            if (result.error) {
                State.toggleTo(State.ERROR, 'Error with payment: ' + result.error);
            } else {
                Receipt.clear();
                State.toggleTo(State.SALES);
            }
        });
    },
    cash: function () {
        console.log('Paying cash');
        var sum = Receipt.getTotal();
        var amount = Math.ceil(sum / 10) * 10;
        State.toggleTo(State.MESSAGE, 'Dat wordt dan &euro; ' + (amount/100).toFixed(2));
    }
};

/*
 * INPUT - processes
 */
Input = {
    prompt: '',
    stroke: function (input) {
        // must be a string
        if (typeof input !== 'string') return;
        // don't allow prepended zeroes
        if (input === '0' && this.prompt === '') return;
        // add to prompt
        this.prompt += input;
        Display.set(this.prompt);
    },
    read: function () {
        // parse the input as integer and pass it on
        return parseInt(this.prompt);
    },
    reset: function () {
        this.prompt = '';
    }
};

User = {
    retrieveData: function (rfid, callback) {
        console.log('RetrieveData called!');
        var data = {
            event_id: Settings.event_id,
            rfid: rfid
        };
        var rpcRequest = {
            jsonrpc: '2.0',
            method: 'juliana.rfid.get',
            params: data,
            id: 1
        };
        console.log('Sending request: ' + JSON.stringify(rpcRequest));
        IAjax.request(rpcRequest, callback);
    },
    check: function (rfid) {
        console.log('Card scanned. Retrieving userData for: ' + rfid);
        State.setLoading();
        User.retrieveData(rfid, function (data) {
            Display.set('?');
            User.continueCheck(data.result.user);
        });
    },
    continueCheck: function (user) {
        console.log(JSON.stringify(user));
        var rpcRequest = {
            jsonrpc: '2.0',
            method: 'juliana.user.check',
            params: {event_id: Settings.event_id, user_id: user.id},
            id: 1
        };
        IAjax.request(rpcRequest, function (data) {
            State.toggleTo(State.MESSAGE, user.first_name + " heeft op deze borrel al &euro;" + (data.result / 100).toFixed(2) + " verbruikt.");
        });
    }
};

IAjax = {
    request: function (data, callback) {
        console.log('IAjax sent: ' + JSON.stringify(data));
        var settings = {
            data: JSON.stringify(data),
            url: Settings.api_url,
            dataType: "json",
            type: "POST",
            success: function (result) {
                console.log('Succesfully sent: ' + result);
                if (callback) {
                    console.log('Response received: calling callback.');
                    callback(result);
                }
            },
            error: function (error) {
                var result = JSON.parse(error.responseText);
                console.log('IAjax request failed');
                State.toggleTo(State.ERROR, result.error.message);
            }
        };
        jQuery.ajax(settings);
    }
};

$(function () {
    Scanner.init();
    State.toggleTo(State.SALES);

    $('.btn').attr('draggable', false).on('dragstart', function () {
        return false;
    });

    $('.btn-keypad').click(function () {
        Input.stroke($(this).html());
    });

    $(document).keydown(function (event) {
        if(event.which >= 48 && event.which <= 57) // 48 is the keycode for 0, 57 for 9
            Input.stroke((event.which - 48).toString());
    });

    $('.command').click(function () {
        var returnValue = undefined;

        switch ($(this).data('command')) {
            case 'clear':
                Display.set('?');
                break;
            case 'sales':
                var count = !Input.read() ? 1 : Input.read();
                Receipt.add($(this).data('product'), count);
                returnValue = false; // don't scroll up after adding a product
                break;
            case 'cancelPayment':
                Receipt.clear();
                // Fall-through on purpose here
            case 'cancelError':
                Display.set('?');
                State.toggleTo(State.SALES);
                break;
            case 'check':
                State.toggleTo(State.CHECK);
                Display.set('Scan een kaart');
                break;
            case 'cash':
                Receipt.cash();
                break;
            case 'payNow':
                Receipt.payNow();
                break;
            case 'payUser':
                var user = { id: $(this).data('user-id'), first_name: $(this).data('user-first-name'), last_name: $(this).data('user-last-name'), alcohol_permitted: true };
                Receipt.payForUser(user, null);
                break;
            case 'ok':
                State.toggleTo(State.SALES);
                break;
            default:
                Display.set('ongeimplementeerde functie');
                Display.flash();
                break;
        }

        Input.reset();
        return returnValue;
    });
});
