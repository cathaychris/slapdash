import * as React from "react";
import axios from "axios";
import buildUrl from "build-url";
import { format_endpoint } from "./app";
import MetadataProps from "./metadata";
import Form from 'react-bootstrap/Form'
import Button from 'react-bootstrap/Button'
import Badge from 'react-bootstrap/Badge'
import InputGroup from 'react-bootstrap/InputGroup'
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import {Tooltip as BootstrapTooltip} from 'react-bootstrap';
import Collapsible from "react-collapsible";

interface MethodProps {
  name: string;
  args: string[];
  doc?: string;
  fullName: string;
  api: string;
  collapsed?: boolean;
  metadata?: MetadataProps;
  gui_alert: (message: string) => void;
}

export default class Method extends React.PureComponent<
  MethodProps,
  { value: any,
    collapsed: boolean }
> {
  constructor(props) {
    super(props);
    this.state = {
      value: null,
      collapsed: localStorage.getItem(props.fullName + '_collapsed') == 'true',
    };

    this.execute = this.execute.bind(this);
  }

  async execute(event: React.FormEvent) {
    event.preventDefault();

    let args = {};
    // leave out empty fields, so that the method's default values apply
    this.props.args.forEach(([name, type]) => {
      if (event.target[name].value !== "") args[name] = event.target[name].value;
    });
    const result = await axios.post(
      buildUrl(this.props.api, {
        path: format_endpoint(this.props.fullName),
        queryParams: args,
      })
    );

    this.setState({ value: result.data });
  }

  render() {
    const hasDoc = ((this.props.doc !== undefined) || (this.props.metadata?.doc !== undefined));
    const docStr = (this.props.metadata?.doc !== undefined) ? this.props.metadata?.doc : this.props.doc;

    const tooltip = (hasDoc) ? (<BootstrapTooltip className="tooltip">{docStr}</BootstrapTooltip>) : null;

    var methodDisplayName = this.props.name;
    if (this.props.metadata?.displayName !== undefined) {
      methodDisplayName = this.props.metadata?.displayName;
    }

    if (this.props.args.length == 0) {
      // return button for functions with no arguments
      if (hasDoc) {
        return (
          <OverlayTrigger
            placement="top"
            overlay={tooltip}
          >
          {({ref, ...triggerHandler }) => (
            <div className="component action" id={this.props.fullName}>
            <Button variant="primary" type="submit" size="sm" onClick={this.execute}>
              <p>{methodDisplayName}</p>
              <Badge pill className="tooltip-trigger" bg="light" text="dark" ref={ref} {...triggerHandler}>?</Badge>
            </Button>
            </div>
          )}
          </OverlayTrigger>
        );
      } else {
        return (
          <div className="component action" id={this.props.fullName}>
          <Button variant="primary" type="submit" size="sm" onClick={this.execute}><p>{methodDisplayName}</p></Button>
          </div>
        )
      }
    }
    const args = this.props.args.map(([name, type], index) => (
      <InputGroup key={index}>
        <InputGroup.Text className="component-label">{name}</InputGroup.Text>
        <Form.Control type="text" name={name}/>
      </InputGroup>
    ));


    const elementProps = { className: "method", id: this.props.fullName };
    // const triggerText = this.props.name + '(' + (this.props.args.map((arg) => arg[0]).join(', '))+')';
    var triggerText = (
      <h3>
        {this.props.name + '('}
        <i>{(this.props.args.map((arg) => arg[0]).join(', '))}</i>
        {')'}
      </h3>
    );

    if (this.props.metadata?.displayName !== undefined) {
      triggerText = (
        <h3>
          {this.props.metadata?.displayName}
        </h3>
      );
    }

    const tooltipStatic = (hasDoc) ? <div className={"method-tooltip"}><Badge pill className="tooltip-trigger" bg="secondary">?</Badge>{docStr}</div> : null;

    return (
      <Collapsible
        containerElementProps={elementProps}
        contentInnerClassName={"method__contentInner"}
        trigger={triggerText}
        transitionTime={200}
        open={this.props.collapsed === undefined ? !this.state.collapsed : !this.props.collapsed}
        onClosing={() => this.setState({collapsed: true})}
        onOpening={() => this.setState({collapsed: false})}
      >
        {tooltipStatic}
        <Form onSubmit={this.execute}>
          {args}
          <div>
            <Button variant="primary" type="submit" size="sm">Execute</Button>
            <div className="result">{this.state.value}</div>
          </div>
        </Form>
      </Collapsible>
    );
  }
}
