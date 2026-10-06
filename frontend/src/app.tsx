import * as React from "react";
import axios from "axios";
import * as _ from "lodash/fp";
import io from "socket.io-client";
import buildUrl from "build-url";
import Form from "react-bootstrap/Form";
import ListGroup from "react-bootstrap/ListGroup";
import Button from "react-bootstrap/Button";
import Badge from "react-bootstrap/Badge";
import { Store, ReactNotifications } from "react-notifications-component";
import Group from "./group";
import { alert_options } from "./alerting";
declare const __SLAPDASH_VERSION__: string; // injected by build.mjs

import "react-notifications-component/dist/theme.css";
import "bootstrap/dist/css/bootstrap.min.css";

function OptionCheckboxes(props) {
  return (
    <ListGroup variant="flush">
      <ListGroup.Item>
        <Form.Switch
          checked={props.instantUpdate}
          onChange={() => props.updater("instant_update", !props.instantUpdate)}
          label={"instant update"}
        />
      </ListGroup.Item>
      <ListGroup.Item>
        <Form.Switch
          checked={props.errorNotifications}
          onChange={() =>
            props.updater("error_notifications", !props.errorNotifications)
          }
          label={"error notifications"}
        />
      </ListGroup.Item>
      <ListGroup.Item>
        <Form.Switch
          checked={props.updateNotifications}
          onChange={() =>
            props.updater("update_notifications", !props.updateNotifications)
          }
          label={"update notifications"}
        />
      </ListGroup.Item>
      <ListGroup.Item>
        <Button
          variant="secondary"
          disabled={false}
          size="sm"
          onClick={() => props.collapseFields()}
        >
          {"collapse all fields"}
        </Button>
      </ListGroup.Item>
      <ListGroup.Item>
        <Button
          variant="secondary"
          disabled={false}
          size="sm"
          onClick={() => props.expandFields()}
        >
          {"expand all fields"}
        </Button>
      </ListGroup.Item>
      <ListGroup.Item>
        <Button
          variant="secondary"
          disabled={false}
          size="sm"
          onClick={() => {
            window.location.href = "/docs";
          }}
        >
          {"see documentation"}
        </Button>
      </ListGroup.Item>
      <ListGroup.Item style={{ textAlign: "center" }}>
        <Badge pill bg="light" text="dark">
          <span>
            Web client version {__SLAPDASH_VERSION__}
          </span>
          <br />
          <span>Server version {props.info.version}</span>
        </Badge>
      </ListGroup.Item>
    </ListGroup>
  );
}

interface AppOptions {
  update_notifications: boolean;
  error_notifications: boolean;
  instant_update: boolean;
  collapsed: boolean | undefined;
}

export default class App extends React.PureComponent<
  { api: string },
  {
    name: string;
    param_value: any;
    param_props: any;
    server_info: any;
    app_options: AppOptions;
  }
> {
  io: SocketIOClient.Socket;

  constructor(props) {
    super(props);

    this.state = {
      name: "Slapdash Interface",
      param_value: {},
      param_props: {},
      server_info: {},
      app_options: {
        update_notifications: false,
        error_notifications: true,
        instant_update: false,
        collapsed: undefined,
      },
    };

    this.update = this.update.bind(this);
    this.update_param = this.update_param.bind(this);
    this.update_option = this.update_option.bind(this);
  }

  async componentDidMount() {
    const name_request = await axios.get(
      buildUrl(this.props.api, { path: "name" })
    );

    const param_request = await axios.get(
      buildUrl(this.props.api, { path: "get_param" })
    );

    const props_request = await axios.get(
      buildUrl(this.props.api, { path: "get_props" })
    );

    const info_request = await axios.get(
      buildUrl(this.props.api, { path: "info" })
    );

    this.setState({
      name: name_request.data,
      param_value: param_request.data,
      param_props: props_request.data,
      server_info: info_request.data,
    });

    // load settings from local storage, or if none there, then from server, or if none sent, then defaults
    if (!(JSON.parse(localStorage.getItem("update_notifications")) == null)) {
      this.update_option(
        "update_notifications",
        JSON.parse(localStorage.getItem("update_notifications"))
      );
    } else if (!(info_request.data.web_settings.update_notifications == null)) {
      this.update_option(
        "update_notifications",
        info_request.data.web_settings.update_notifications
      );
    }

    if (!(JSON.parse(localStorage.getItem("error_notifications")) == null)) {
      this.update_option(
        "error_notifications",
        JSON.parse(localStorage.getItem("error_notifications"))
      );
    } else if (
      !(info_request.data.web_settings.exception_notifications == null)
    ) {
      this.update_option(
        "error_notifications",
        info_request.data.web_settings.exception_notifications
      );
    }

    if (!(JSON.parse(localStorage.getItem("instant_update")) == null)) {
      this.update_option(
        "instant_update",
        JSON.parse(localStorage.getItem("instant_update"))
      );
    } else if (!(info_request.data.web_settings.instant_update == null)) {
      this.update_option(
        "instant_update",
        info_request.data.web_settings.instant_update
      );
    }

    if (name_request.data) {
      document.title = `${name_request.data} - Slapdash Interface`;
    }

    this.io = io(this.props.api, { path: "/ws/socket.io" });
    this.io.on("connect", () => {});
    this.io.on("disconnect", () => {});
    this.io.on("notify", (msg) => {
      if (typeof msg.data.name !== "undefined") {
        this.update_param(msg.data.name, msg.data.value);
        // default for updates will be to NOT display them
        if (this.state.app_options.update_notifications === true) {
          this.send_info(
            "Variable `" +
              msg.data.name +
              "` updated to `" +
              msg.data.value +
              "`"
          );
        }
      }
      if (typeof msg.data.exception !== "undefined") {
        // default for exceptions will be to DISPLAY them
        if (this.state.app_options.error_notifications === true) {
          this.send_alert(msg.data.type, msg.data.exception);
        }
      }
    });
  }

  update_param(name: string, value: any) {
    // updates param in app state
    const param_value = _.set(name, value, this.state.param_value);
    this.setState({ param_value: param_value });
  }

  update_option(name: string, value: any) {
    // updates option param in app state
    const param_value = _.set(name, value, this.state.app_options);
    this.setState({ app_options: param_value });
    localStorage.setItem(name, JSON.stringify(value));
  }

  reset_collapse() {
    var param_value = this.state.app_options;
    // delete param_value.collapsed;
    param_value.collapsed = undefined;
    setTimeout(() => {
      this.setState({ app_options: param_value });
    }, 210);
  }

  trigger_collapse(value: boolean) {
    var param_value = _.set("collapsed", value, this.state.app_options);
    this.setState({ app_options: param_value }, () => {
      this.reset_collapse();
    });
  }

  send_info(value: string) {
    Store.addNotification({
      ...alert_options,
      message: value,
      title: "Update notification",
      type: "info" as const,
    });
  }

  send_alert(type: string, value: string) {
    Store.addNotification({
      ...alert_options,
      message: value,
      title: "Exception (" + type + ")",
      type: "danger" as const,
    });
    // passes error messages along to users
  }

  send_gui_alert(message: string) {
    Store.addNotification({
      ...alert_options,
      message: message,
      title: "GUI message",
      type: "warning" as const,
    });
  }

  fnNull(message: string) {
    const a = 0;
  }

  async update(name: string, value: any) {
    const url = buildUrl(this.props.api, { path: format_endpoint(name) });
    const result = await axios.post(url, null, { params: { value: value } });
    this.update_param(name, result.data);
  }

  render() {
    return (
      <div id="slapdash">
        <div id="slapdash-options">
          <OptionCheckboxes
            instantUpdate={this.state.app_options.instant_update}
            errorNotifications={this.state.app_options.error_notifications}
            updateNotifications={this.state.app_options.update_notifications}
            updater={this.update_option}
            collapseFields={() => {
              this.trigger_collapse(true);
            }}
            expandFields={() => {
              this.trigger_collapse(false);
            }}
            api={this.props.api}
            info={this.state.server_info}
          />
          <div className="options">
            <span>▼ OPTIONS ▼</span>
          </div>
        </div>
        <ReactNotifications />
        <Group
          name={this.state.name}
          param_value={this.state.param_value}
          param_props={this.state.param_props}
          update={this.update}
          api={this.props.api}
          collapsible={false}
          collapsed={this.state.app_options.collapsed}
          instant_update={this.state.app_options.instant_update}
          gui_alert={
            this.state.app_options.error_notifications === true
              ? this.send_gui_alert
              : this.fnNull
          }
        />
      </div>
    );
  }
}

export function format_endpoint(endpoint: string): string {
  return endpoint.replace(/\./g, "/").replace(/\[/g, "/").replace(/\]/g, "");
}
