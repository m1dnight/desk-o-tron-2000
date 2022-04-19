    const app = Vue.createApp({
        watch: {
            sitHeight: function (newValue, oldValue) {
                if (oldValue != null) {
                    command = {"command": "set_sit", "value": newValue}
                    this._connection.send(JSON.stringify(command))
                }
            },
            standHeight: function (newValue, oldValue) {
                if (oldValue != null) {
                    command = {"command": "set_stand", "value": newValue}
                    this._connection.send(JSON.stringify(command))
                }
            },
            standDuration: function (newValue, oldValue) {
                if (oldValue != null) {
                    command = {"command": "set_stand_duration", "value": newValue}
                    this._connection.send(JSON.stringify(command))
                }
            },
            sitDuration: function (newValue, oldValue) {
                if (oldValue != null) {
                    command = {"command": "set_sit_duration", "value": newValue}
                    this._connection.send(JSON.stringify(command))
                }
            }
        },
        methods: {
            sit() {
                command = {"command": "sit"}
                this._connection.send(JSON.stringify(command))
            },
            stand() {
                command = {"command": "stand"}
                this._connection.send(JSON.stringify(command))

            },
            handle_message(message) {
                if ("current_height" in message) {
                    this.height = parseFloat(message['current_height']);
                    return
                }
                if ('config' in message) {
                    console.log(message)
                    this.sitHeight = message.config.sit
                    this.standHeight = message.config.stand
                    this.sitDuration = message.config.sit_duration
                    this.standDuration = message.config.stand_duration
                } else {
                    console.log("Message not understood:" + JSON.stringify(message))
                }
            },
            start(e) {
                if (e === 'fullDown') {
                    this.sit()
                }
                if (e === 'fullUp') {
                    this.stand()
                }
                if (e === "up" || e === "down") {
                    if (!this._clicking) {
                        let command = {"command": e === "up" ? "move_up" : "move_down"}
                        this._connection.send(JSON.stringify(command));
                        this._clicking = setInterval(() => {
                            let command = {"command": e === "up" ? "move_up" : "move_down"}
                            this._connection.send(JSON.stringify(command));
                        }, 100);
                    }
                }
            },
            stop() {
                clearInterval(this._clicking)
                this._clicking = false;
            },
            round(n) {
                return Math.trunc(n * 100) / 100;
            }
        },
        data() {
            return {
                height: null,
                sitHeight: null,
                standHeight: null,
                standDuration: null,
                sitDuration: null,
                _clicking: false,
                _maxHeight: 650,
                _minHeight: 0,
                _connection: null,
                standingSince: null,
                sittingSince: null
            }
        },
        computed: {
            heightPercent: function () {
                let percent = this.height  / this._maxHeight * 100;
                console.log(percent)
                return Math.trunc(percent * 100) / 100;
            }
        },
        mounted: function () {
            // Connect to the webserver when the webapp launches.
            this._connection = new WebSocket('ws://localhost:8080/websocket')

            // Dispatch each incoming message to the handle_message functin.
            this._connection.onmessage = (event) => {
                console.log(event);
                this.handle_message(JSON.parse(event.data));
            }

            // When the connection is established, send a ping.
            this._connection.onopen = (event) => {
                this._connection.send(JSON.stringify({"command": "current_height"}));
                this._connection.send(JSON.stringify({"command": "get_config"}));
            }
        }
    })

    app.mount('#shopping-list')