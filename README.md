# Wallpad server for Home Assistant

A Home Assistant custom integration that shows where the elevator cars are and calls one, through a
wallpad server's API.

## Entities

All of them belong to one device, `Elevator`.

| Entity | What it does |
|---|---|
| `sensor.elevator_car_N` | The floor car N is on, for example `6F` or `B2`. `F` means between floors, and the state is `unknown` when the server has no floor for that car. One sensor per car the server reports. |
| `button.elevator_call_up` | Calls a car to go up from this household's floor. |
| `button.elevator_call_down` | Calls a car to go down from this household's floor. |

Everything is `unavailable` while the connection to the server is down. A press that fails shows an
error in Home Assistant and is never resent, so press again if you still want the car.

## Install

1. Copy `custom_components/wallpad_server` into the `custom_components` folder of your Home
   Assistant configuration directory, the one holding `configuration.yaml`. Create the folder if it
   does not exist.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration**, choose **Wallpad server**, and enter
   your server's host and port.

To update, copy the folder again and restart.

## How it talks to the server

| Path | Used for |
|---|---|
| `GET /api/v1/features` | Checking that the server offers the `elevator` feature with both calls |
| `WS /api/v1/ws` | Receiving status as it changes, and sending the `call-up-here` and `call-down-here` controls |

The floors come from the elevator status's `cars` field. Status is pushed, so nothing is polled.
The server's API has no authentication, so keep it on a network you trust.

## Development

Needs the Python version the pinned Home Assistant requires.

```bash
pip install -r requirements-test.txt
```

```bash
python -m ruff check .
```

```bash
python -m pytest
```
