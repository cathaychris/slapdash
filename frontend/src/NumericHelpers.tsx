import NumericInput from "./NumericInput";
import {ComponentType} from "./component";

const RE_LEADING_ZERO_NUM  = /^([+-]?)((\.\d+)|([1-9]+(\.\d+)?)|((0+)([1-9]+\d*(\.\d+)?)))$/;
const RE_NUMBER            = /^[+-]?((\.\d+)|([1-9]+(\.\d+)?))$/;
const RE_INCOMPLETE_NUMBER = /^([+-]0?|[0-9]*\.0*|[+-]\.0*|[+-]?\d+\.)?$/;

function stringPrecision(stringInput: string) {
    // console.log('== Calculating precision in stringPrecision');
    // Calculate the precision of a number rendered as a string.
    if (stringInput.indexOf('.') < 0) {
      // console.log('  stringPrecision has no decimal, returning zero');
      return 0;
    } else {
      // console.log('  stringPrecision has a decimal, returning '+(stringInput.length - stringInput.indexOf('.') - 1));
      return stringInput.length - stringInput.indexOf('.') - 1 // -1 to remove width of decimal
    }
  }

function truncateDecimals(n: number) {
  // console.log('== Truncating decimals in truncateDemicals');
  return Math[n < 0 ? 'ceil' : 'floor'](n);
};

export function fnCalcPrecision(componentProps: any) {
    // this function is called when formatting functions, which occurs during a component render
    //    (e.g. onFocus; in this case, the selection will still be undefined)
    // the new value will be present in the component state, but maybe not the stringValue because we haven't formatted yet?
    // --> no, stringValue should be without formatting

    return (component: NumericInput, step?: number) => {
        // console.log('== [fnCalcPrecision] Calculating precision in fnCalcPrecision');

        // need to predict how the formatting of the string will change the cursor position, primarily before the decimal place
        // e.g. 0001234| will become 1234|
        // e.g. -0001234| will become -1234|
        // e.g. 001|002003004 will become 1|002003004
        // e.g. -001|00.1234 will become -1|00.1234
        // let formattingLengthDiff = (component.state.value != undefined && component.refsInput.value != undefined) ? component.state.value?.toString().length-component.refsInput.value.length : 0;
        // console.log('[fnCalcPrecision]   state value is ' + component.state.value + ' and field value is ' + component.refsInput.value);

        let formattingLengthDiff = 0;
        let m;
        if ((m = RE_LEADING_ZERO_NUM.exec(component.refsInput.value)) !== null) {
            m.forEach((match, groupIndex) => {
              // console.log(`Found match, group ${groupIndex}: ${match}`);
              if (groupIndex == 7) { // match with leading zeros
                if (match != undefined) {
                  formattingLengthDiff = match.length;
                }
              }
            });
        }

        // BUG: typing -0001|234.5678 sometimes returns -1234|.5678 and sometimes -1|234.5678 (like it should)

        const integerType: boolean = (componentProps.type === ComponentType.Int);
        if (integerType) {
            // console.log('[fnCalcPrecision]  sensed integer type; force zero precision');
            return 0;
        }

        var stringInput = component.state.stringValue; // should be trimmed already; it's the state value + ''
        if (stringInput === undefined) {
            stringInput = '';
        }
        // console.log('[fnCalcPrecision]  in calcPrecision, values are (value: ' + component.state.value + ', stringValue: ' + component.state.stringValue + ')')

        var cursStart = component.state.selectionStart ? component.state.selectionStart : stringInput.length;
        var cursEnd = component.state.selectionEnd ? component.state.selectionEnd : stringInput.length;
        // Causes bug: trailing precision is lost when passing through a lower-precision value (e.g. moving down from 123.0001|)
        // // Prevent bug: if we type a short number and click away, the selection will be at a position longer than the new string itself
        // if (cursStart > stringInput.length) {
        //   // console.log('[fnCalcPrecision]  WARNING: cursor start was truncated')
        //   cursStart = stringInput.length;
        // }
        // if (cursEnd > stringInput.length) {
        //   // console.log('[fnCalcPrecision]  WARNING: cursor end was truncated')
        //   cursEnd = stringInput.length;
        // }
        // console.log('[fnCalcPrecision]  selection window is (' + cursStart + ', ' + cursEnd + ')')

        // if step is nonzero, this is being called as part of toNumber as part of an updated value calculation (first time this is called)
        const stepBasedPrecision = step ? Math.min(Math.max(-Math.log10(Math.abs(step)), 0), 100) : 0;
        // console.log('  supplied step is ' + step + ', suggesting precision ' + stepBasedPrecision);
        // return the more precise of the setting value and existing number
        if (step) {
            let initialPrecision = stringPrecision(stringInput);
            let newPrecision = Math.max(initialPrecision, stepBasedPrecision);
            // console.log('[fnCalcPrecision]  setting precision to more precise of (initialPrecision, stepBasedPrecision) = (' + initialPrecision + ', ' + stepBasedPrecision + ') is ' + newPrecision);
            return newPrecision;
        }

        // gives absolute value of step size caused by a re-render from a step (if !==0, will be the second time calcPrecision is called when setting)
        if (component.state.value !== null && component.state.value !== undefined) {
          const inferredLastStep = Math.abs(component.state.value - component.props.value); // these will differ during a re-render until onChange is called
          // console.log('[fnCalcPrecision]  props value ' + component.props.value + ' and state value ' + component.state.value + '; inferred step to be ' + inferredLastStep);
          if (inferredLastStep !== 0) {
              let inferredStepPrecision = Math.round(-Math.log10(inferredLastStep));
              // console.log('[fnCalcPrecision]  as part of a re-render, setting precision to inferred precision ' + inferredStepPrecision + ' based on step size');
              let mostPrecise = Math.max(inferredStepPrecision, stringPrecision(component.props.value + ''), stringPrecision(component.state.value + ''));
              // console.log('[fnCalcPrecision]  most precise of old/new/inferred values is ' + mostPrecise);
              return mostPrecise;
        }}

        if (component.state.selectionEnd === undefined) {
            // the input is not in focus and so we do not relegate precision to anything in particular
            // console.log('[fnCalcPrecision]  No selection defined for component; leaving precision `null`');
            return null;
        }

        let floatZero: boolean = component.state.value == 0; // special treatment required to distinguish -0 and 0
        let stringMinus: boolean = stringInput[0] == '-';
        let minusZero: boolean = floatZero && stringMinus;
        if (minusZero) {
          // console.log('[fnCalcPrecision]  WARNING: minus zero detected');
        }
        let numericPrecision = stringPrecision(stringInput);
        let existsDecimal: boolean = (stringInput.indexOf('.') >= 0);
        // let existsMinus: boolean = (stringInput.indexOf('-') >= 0);
        // if there is a decimal point, the cursor precision is just the position after the decimal minus the width of the decimal
        // if there is no decimal point, we may be at an integer (123.999| -> 124____|) so need to imagine the decimal were there
        let cursorAdjusted = cursEnd - 1; // remove decimal width
        let cursorPrecision = existsDecimal ? cursorAdjusted - stringInput.indexOf('.') : cursorAdjusted - stringInput.length;
        
        // if props value and state value same, but state value and field value different, then change
        // we only want where the cursor is at the position where it would cause this change
        // cursor will have selection window 0 length; arrow will have 1 length, except at first movement
        if (formattingLengthDiff !== 0) {
          if (true) {
            let fromTyping = (cursStart == cursEnd) && (cursStart !== stringInput.length); // avoid the undefined case
            if (fromTyping) { // only apply when the formatting change occurs from typing and not at the end
              // console.log('[fnCalcPrecision]   starting state cursor (' + component.state.selectionStart + ', ' + component.state.selectionEnd + ')');
              // console.log('[fnCalcPrecision]   starting ref cursor (' + component.refsInput.selectionStart + ', ' + component.refsInput.selectionEnd + ')');
              component.state.selectionStart = cursStart - formattingLengthDiff;
              component.state.selectionEnd = cursEnd - formattingLengthDiff;
              // console.log('[fnCalcPrecision]  [INACTIVE] detected a formatting change causing a cursor shift of ' + formattingLengthDiff + ' places'); // to (' + component.state.selectionStart + ', ' + component.state.selectionEnd + ')');
              component.refsInput.selectionStart = component.state.selectionStart; // just to be sure
              component.refsInput.selectionEnd = component.state.selectionEnd;
            }
          }
        }

        let cursorBasedPrecision = Math.max(numericPrecision, cursorPrecision);
        // console.log('  [fnCalcPrecision] setting precision to more precise of (numericPrecision, cursorPrecision) = (' + numericPrecision + ', ' + cursorPrecision + ') is ' + cursorBasedPrecision);
        return cursorBasedPrecision;
    }
}

export function fnCalcStep(componentProps: any) {
    return (component: NumericInput, direction: NumericInput.direction) => {
    // this function is called when calculating the new value and stringValue states
    // after this function runs, setState is called and a render will be prompted

    // console.log('== Calculating step size in fnCalcStep');
    componentProps.ensureEdit();
    if (component.state.stepMultiplier == undefined ) {
      component.state.stepMultiplier = 1;
    }
    if (componentProps.step !== undefined) {
      return componentProps.step;
    } else {
      const stringInput: string = component.refsInput.value.trim(); // current value without space at end, including any trailing zeros from precision/formatting
      const numInput: number = (component.state.value !== undefined && component.state.value !== null) ? component.state.value : 0; // numeric starting value
      const integerType: boolean = (componentProps.type === ComponentType.Int);
      // console.log('  [fnCalcStep] starting stringInput: ' + stringInput);

      if (component.state.selectionStart == undefined) { // default behavior at init
        // console.log('  [fnCalcStep] selection start undefined');
        const decimal = stringInput.indexOf(".");
        // component.setState((state, props) => ({selectionStart: state.stringValue.trim().length-1, selectionEnd: state.stringValue.trim().length}), notifySet());
        component.state.selectionStart = stringInput.length - 1;
        component.state.selectionEnd = stringInput.length;
        component.refsInput.selectionStart = component.state.selectionStart; // just to be sure
        component.refsInput.selectionEnd = component.state.selectionEnd;

        if (decimal >= 0) { // step should be the smallest existing digit
          return Math.pow(10, -1*stringInput.slice(decimal, -1).length)
        } else {
          return 1 // no decimal means we render as an integer, so smallest possible step is 1
        }

      } else {
        // console.log('  [fnCalcStep] selection start defined');
        let digitsMatch = stringInput.match(/^[+-]?(\d+)(\.\d+)?$/);
        const digits = (digitsMatch !== null) ? digitsMatch[1].length : 0; // # of unsigned numeric digits before decimal incl. 0s
        // console.log('  [fnCalcStep] current integer digits from regex: '+ digits);
        // get the current cursor position
        const sEnd: number = (component.state.selectionEnd !== undefined && component.state.selectionEnd !== null) ? component.state.selectionEnd : 0;
        // cursor should represent the selection end of numeric digits
        let cursor: number = sEnd;
        // get the digit of the decimal mark
        const decimal = stringInput.indexOf(".");
        // initialize the minimum digit that can be selected
        let minCursorDigit: number = 0;

        
        if (decimal == 0) {
          // if the decimal is sitting at the very left, we cannot be before it;
          // we must always be selecting a digit to the left
          // -> but this means we have a value < 1, so increasing the digit means a step of 1
          minCursorDigit += 1;
          // var nope = null;
          // TODO: probably add a preceding zero for consistency, and deal with the numeric zero case
        }
        if (cursor > decimal && decimal >= 0) {
          // if the cursor is to the right of the decimal, compensate, because
          // `cursor` should represent selection end, counting total numeric digits
          cursor -= 1;
        }
        // compensate for the space taken up by the '-' sign
        if (numInput < 0) {
          cursor -= 1;
          minCursorDigit += 1;
        }

        // console.log('  [fnCalcStep] cursor: '+cursor);
        // digits-cursor gives the cursor position after the decimal, will be 0 if no decimals
        // digits-1 gives the highest possible step, e.g. 10^3 if the number is 5|000
        // we take the smaller of the two, limiting the maximum step
        // a negative value in the min() argument means smaller steps
        var newStep: number = Math.pow(10, Math.min(digits - cursor, digits));
        // console.log('  [fnCalcStep] initial new step: ' + newStep);
        if (integerType) { // restrict to integer values, minimum step size thus 1
          newStep = Math.max(newStep, 1);
        }

        const newValue: number = (direction === NumericInput.DIRECTION_UP) ? (component.state.value + newStep) : (component.state.value - newStep);
        // console.log('  [fnCalcStep] numeric newValue: ' + newValue);

        var oldPrecision = 0; // default for integers
        if (!integerType) {
          if (stringInput.indexOf('.') >= 0) { // decimal exists
            oldPrecision = stringInput.length - stringInput.indexOf('.') - 1 // -1 to remove width of decimal
          }
        }
        // console.log('  [fnCalcStep] inferred old precision: ' + oldPrecision);
        const newPrecision = Math.max(-Math.log10(newStep), oldPrecision);
        // console.log('  [fnCalcStep] ideal new precision based on new step size: ' + newPrecision);
        const newValueRound: string = newValue.toFixed(newPrecision); // this emulates what will be given to the formatter, e.g. -1.234
        const newLength: number = newValueRound.length; // total characters including - and . ; does not include trailing space
        const maxCursorDigit = (integerType) ? newLength : newLength+1; // don't allow to add precision if integer, otherwise, we can go to end
        const newDecimal = newValueRound.indexOf("."); // -1 if none, else position of new decimal

        // really the length change of the absolute integer part of the number, so neglecting minus signs
        // by implementing the leading-zero padding formatter, we should not produce a REDUCING length change from the integer part anymore, so start with 0 here
        var lengthChange: number = 0;
        // console.log('  [fnCalcStep] length change calculated as ' + Math.abs(newValue).toFixed().length + ' - ' + Math.abs(numInput).toFixed().length + ' = ' + lengthChange);

        // if we will DECREASE the number of integer digits and the cursor was not at the leading digit, we will lose one zero
        const intDecrease: boolean = (truncateDecimals(Math.abs(newValue)).toString().length - digits < 0) && sEnd !== minCursorDigit+1;
        if (intDecrease) { // can only decrease by one power at a time if not on leading digit (can't cross minus)
          // console.log('  [fnCalcStep] sensed integer value length decrease ( from '+ digits +' to '+ truncateDecimals(Math.abs(newValue)).toString().length +' ) with cursor at minimum')
          lengthChange -= 1;
        }

        // however if we INCREASE the number of integer digits we will want to shift right
        // (truncate doesn't account for 0s, digits does, but doesn't matter for an increase which must come from a starting non-zero digit)
        const intIncrease: boolean = (truncateDecimals(Math.abs(newValue)).toString().length - digits > 0);
        if (intIncrease) { // can only increase by one power at a time
          // console.log('  [fnCalcStep] sensed integer value length increase ( from '+digits+' to '+truncateDecimals(Math.abs(newValue)).toString().length+' )');
          lengthChange += 1;
        }

        // if our new value removes or adds a minus sign, move the selection left or right respectively
        // Math.sign returns -1, +/-0, or +1, so only count changes that go -1 <-> +1
        // this can miss the change when going to/from exactly ZERO
        // const signChange: boolean = Math.abs(Math.sign(newValue) - Math.sign(numInput)) > 1;
        const signChange = newValue.toString().indexOf('-') !== numInput.toString().indexOf('-');
        if (signChange) {
          // console.log('  [fnCalcStep] sensed sign change: new sign ' + Math.sign(newValue) + ' and old sign ' + Math.sign(numInput));
          lengthChange = (newValue.toString().indexOf('-') >= 0) ? lengthChange + 1 : lengthChange -1;
        }

        // if our new value adds a decimal point, move the selection left or right to account for length change
        const decimalChange: boolean = ((stringInput.indexOf('.') < 0) !== (newDecimal < 0));
        if (decimalChange) {
          // console.log('  [fnCalcStep] with string input ' + stringInput + ': sensed addition of decimal point (at position ' + newDecimal + ', forming new value ' + newValueRound + ')');
          lengthChange = (newDecimal < 0) ? lengthChange - 1 : lengthChange + 1;
        }

        // console.log('  [fnCalcStep] length change calculated to be ' + lengthChange);

        // prevent overrun of cursor position by clamping its position
        // console.log('  [fnCalcStep] minimum cursor digit is ' + minCursorDigit);
        // console.log('  [fnCalcStep] maximum cursor digit is ' + maxCursorDigit);
        // console.log('  [fnCalcStep] current selection end is ' + sEnd);
        // the new selection end will be the former selection end plus the length change due to integer part length change (1001 -> 1), and decimal and sign change
        // the maximum it can be is the length of the new number
        var newEnd = Math.min(Math.max(sEnd + lengthChange, minCursorDigit), maxCursorDigit);
        // the new selection start will be one less than the new end, but we can't go left of a decimal or a minus sign
        var newStart = Math.min(Math.max(newEnd - 1, minCursorDigit), maxCursorDigit);
        // console.log('  [fnCalcStep] new start and end are (' + newStart + ',' + newEnd + ')');

        // now perform checks to make sure we didn't mess up... ideally deal with these earlier though
        // shift selection window left if we are to the right of a decimal
        if (!integerType) {
          if (newDecimal >= 0 && newEnd == newDecimal+1) {
            // console.log('  [fnCalcStep] sensed sub-one precision for integer type; shifting selection left by 1');
            newStart -= 1;
            newEnd -= 1;
          }
        }

        // shift insertion cursor right if there is a minus sign (will fail for -.1?)
        if (newValue < 0 && newEnd == 1) {
          // console.log('  [fnCalcStep] sensed minus sign; increase selection by one');
          newStart += 1;
          newEnd += 1;
        }

        // if we have run up against a limit, shift start left to select 1 digit instead of 0
        // this would have been a problem earlier already, since the former checks move both start and end
        if (newEnd == newStart) {
          // console.log('  [fnCalcStep] run up against a limit (newStart '+newStart+', newEnd '+newEnd+'), shift start left one');
          newStart -= 1;
          // TODO: check if this is a start or end limitation, and if it's a start limitation we need to add a leading zero
        }

        // console.log('  [fnCalcStep] Setting selection to (' + newStart + ',' + newEnd + ')');
        component.state.selectionStart = newStart;
        component.state.selectionEnd = newEnd;
        component.refsInput.selectionStart = component.state.selectionStart; // just to be sure
        component.refsInput.selectionEnd = component.state.selectionEnd;
        // if the input does not allow us to move the selection window beyond the number of digits,
        // the saveSelection function will take in the wrong value as our selection state
        return newStep;
      }
    }
  }
}

export function fnClampNumericTyping(props) {
  return (event: any, component: NumericInput) => {
    // console.log('== Clamping numeric typing in fnClampNumericTyping');
    // console.log(event);
    let value = event.target.value + '';
    let sStart = event.target.selectionStart;
    let sEnd = event.target.selectionEnd;
    let char = event.key;
    let newString = value.slice(0, sStart) + char + value.slice(sEnd);
    // console.log('   newString in fnClampNumericTyping: ' + newString);

    let newValue = component._parse(newString);
    let insertionNonZero = /^[1-9]+$/.test(char);

    let truncatedNewString = newValue.toString();
    // compare to newString, which will include any preceding zeros
    // if a character is inserted (not an arrow key pressed) with leading zeros,
    // remove them and shift the selection accordingly
    let formattingLengthDiff = 0;
    let m;
    if ((m = RE_LEADING_ZERO_NUM.exec(newString)) !== null) {
        m.forEach((match, groupIndex) => {
            if (groupIndex == 7) { // match with leading zeros
              if (match != undefined) {
                formattingLengthDiff = match.length;
              }
            }
        });
    }

    let loose = !component._isStrict && (component._inputFocus || !component._isMounted)
    let noReRender = (loose && RE_INCOMPLETE_NUMBER.test(newString)) || (loose && newString && !RE_NUMBER.test(newString));
    // console.log('   guess that component will remain static without re-rendering? ' + noReRender);

    // BUG: starting with -89, typing -00089 and then moving with arrows and adding a 1 to get -01|0089 actually gives -10|089
    // this is a case where the field is not re-rendered, and so needs to be handled here

    if (component.props.min !== undefined) {
      if (newValue < component.props.min) {
        event.preventDefault();
        component.saveSelection();
        props.gui_alert('Value of ' + props.fullname + ' cannot go below ' + props.min + '.');
        // console.log('   Value of ' + props.fullname + ' cannot go below ' + props.min + '.');
        component.refsInput.setValue(component._format(component.props.min, 0));
      }
    }

    if (component.props.max !== undefined) {
      if (newValue > component.props.max) {
        event.preventDefault();
        component.saveSelection();
        props.gui_alert('Value of ' + props.fullname + ' cannot exceed ' + props.max + '.');
        // console.log('   Value of ' + props.fullname + ' cannot exceed ' + props.max + '.');
        component.refsInput.setValue(component._format(component.props.max, 0));
      }
    }

    // deal with re-rendering insertions in fnCalcPrecision
    // console.log("   non-rerender formatting status: " + (formattingLengthDiff > 0) + ', ' + noReRender + ', ' + insertionNonZero);
    // if ((formattingLengthDiff > 0) && noReRender && insertionNonZero) {
    //   // console.log('   non-rerender starting state cursor (' + sStart + ', ' + sEnd + ')');
    //   // console.log('   non-rerender starting state cursor (' + component.state.selectionStart + ', ' + component.state.selectionEnd + ')');
    //   // console.log('   non-rerender starting ref cursor (' + component.refsInput.selectionStart + ', ' + component.refsInput.selectionEnd + ')');
    //   // component.state.selectionStart = sStart + 1 - formattingLengthDiff; // inserted char: length 1
    //   // component.state.selectionEnd = sEnd + 1 - formattingLengthDiff;
    //   // console.log('   detected a non-rerender formatting change causing a cursor shift of -' + formattingLengthDiff + ' places from ' + newString + ' to ' + truncatedNewString);
      // component.refsInput.selectionStart = component.state.selectionStart; // just to be sure
      // component.refsInput.selectionEnd = component.state.selectionEnd;
      // BUG: this will not move the cursor without changing where the number is inserted!
    // }
  }
}

export function handleNumericKeyDown(event: any, component: NumericInput) {
    event.preventDefault(); // prevent default to manually enter character later
    // deal with the formatter causing shifts while typing
    // console.log('== Detected typing of a number in handleNumericKeyDown');
    let value = component.refsInput.value, length = value.length;
    let sStart = component.refsInput.selectionStart;
    let sEnd = component.refsInput.selectionEnd;
    let char = event.key;
    let newString = value.slice(0, sStart) + char + value.slice(sEnd);
    component.refsInput.value = newString; // manually enter character to prevent auto cursor move
    // console.log('   ...detected insertion of a number `' + char + '` between ' + value.slice(0, sStart) + ' and ' + value.slice(sEnd) + ', taking ' + value + ' to new string ' + newString);
    let fOld = component._format(component._parse(value), 0);
    let fNew = component._format(component._parse(newString), 0);

    // deal with change of cursor precision positioning as a result of this typing insertion
    // let lengthChange = fNew.length - newString.length + char.length; // - 1; // counteract default input behavior
    // let lengthChange = fNew.trim().length - value.trim().length + char.length;

    // length change not considering formatting:
    // console.log('   ...unformatted values would go from `' + value + '` to `' + newString + '` (' + (newString.trim().length - value.trim().length) + ')');
    let absLengthChange = newString.trim().length - value.trim().length; // includes character length

    // console.log('   ...strictly formatted values would go from `' + fOld + '` to `' + fNew + '` (' + (fNew.trim().length - fOld.trim().length) + ')');
    // let absLengthChange = newString.trim().length - value.trim().length; // includes character length

    // we would expect formatting to only change by char.length unless it does something weird (e.g. truncating):
    // console.log('   ...formatted values are expected to go from `' + value + '` to `' + fNew + '` (' + (fNew.trim().length - value.trim().length) + ')');
    let netFormatLengthChange = fNew.trim().length - value.trim().length - (char.length - (sEnd - sStart));

    let lengthChange = absLengthChange + netFormatLengthChange;
    // console.log('   ...calculating length change as ' + absLengthChange + ' + ' + netFormatLengthChange + ' = '+ lengthChange);

    // account for formatting causing a change in precision
    if (value.slice(0, sStart).indexOf('.') >= 0) {
        lengthChange += 1;
        // console.log('   ...and adding +1 because right of the decimal position')
        if (value.trim().slice(-1) == '.') { // don't shift right after the decimal point with nothing else present
        lengthChange -= 1;
        // console.log('   ...and adding -1 because right after the decimal')
        } else if (newString.trim().slice(-2, -1) == '0') {
        lengthChange -= 1;
        // console.log('   ...and adding -1 because of zero formatting')
        }
    }

    // account for replacing a valueful number with a number with lots of trailing zeros after the decimal

    // if length increases but then we truncate because of precision, we can get into trouble here
    // console.log('   ...so shifting selection (' + component.state.selectionStart + ',' + component.state.selectionEnd + ') by '+ lengthChange);
    // console.log('...so shifting selection (' + component.refsInput.selectionStart + ',' + component.refsInput.selectionEnd + ') by '+ lengthChange);
    let newCursor = component.state.selectionStart + lengthChange;
    if (value.slice(0, sStart+1).indexOf('.') < 0) {
        newCursor = component.state.selectionEnd + lengthChange;
    }

    component.state.selectionEnd = component.refsInput.selectionEnd = newCursor;
    component.state.selectionStart = component.refsInput.selectionStart = newCursor;
    component.saveSelection();
    // console.log('   ...so shifting selection to ('+ component.refsInput.selectionStart + ',' + component.refsInput.selectionEnd + ') and setting value ' + component._parse(newString));

    let fNewNew = component._format(component._parse(newString), 0);
    // console.log('   ...and after cursor move, expect a formatted value ' + fNewNew);

    component.refsInput.setValue(newString);

}

export function simplePadder(n: number) {
    // console.log('calling formatter with simplePadder on number '+n);
    return n.toString().replace(/^\s+|\s+$/g, '') + "";
}

export function simpleCleaner(n: number) {
  // console.log('calling formatter with simpleCleaner on number ' + n);
  let s = n.toString().replace(/\s+/g, ''); // remove all whitespace characters
  // console.log('cleaning number up from ' + n + ' to ' + s);
  let splitDecimals = s.split(".");
  var joinDecimals = splitDecimals[0];
  if (splitDecimals.length > 1) {
    joinDecimals += ("." + splitDecimals.slice(1).join(""));
  }
  // console.log('new number minus padding is '+ joinDecimals);
  return joinDecimals + "";
}

export function leadingZeroPadder(n: number, integerDigits: number | null = null) {
    // accepts a value (`n`) and the number of digits (`integerDigits`) we want to precede the decimal point (if one exists)
    // if `integerDigits` is more than the current digits, we will pad `n`'s integer part with zeros;
    // otherwise, does not truncate, just does nothing
    // console.log('inside leading-zero formatter leadingZeroPadder on number '+n);
    let paddedValue: string = simpleCleaner(n);
    // if (integerDigits && integerDigits > 1) { // non-zero value (2 or higher)
    if (integerDigits) { // non-zero value (1 or higher)
        let precedingDigits: number = truncateDecimals(Math.abs(n)).toString().length; // will give 1 or higher
        let startingIndex: number = (paddedValue.indexOf('-') >= 0) ? paddedValue.indexOf('-') + 1 : 0; // account for width of '-'
        // console.log('...preceding digits of `' + n + '` counted up to be ' + precedingDigits);
        // console.log('...requested digits of `' + n + '` are ' + integerDigits);
        let digitsToPadWith = integerDigits-precedingDigits;
        if (digitsToPadWith > 0) {
        let padString = '0'.repeat(digitsToPadWith);
        // console.log('...leading-zero padder inserted `' + padString + '` into ' + paddedValue);
        paddedValue = paddedValue.slice(0, startingIndex) + padString + paddedValue.slice(startingIndex);
        }
    }
    return paddedValue + "";
}

export function precisionFormatter(n: number, stepSize: number) {
    // the leadingZeroPadder wants a number to pad to;
    // using the integer part of the last step size, we will ask to pad to
    // 1 if the step size is <= 1
    // stepSize.length if the step size is >= 5
    // (this is OK because we will only have powers of 10 anyway)
    // console.log('== Formatting precision in precisionFormatter');
    if (stepSize !== undefined) {
      let l = stepSize.toFixed().length;
      // console.log('  Formatter calling leadingZeroPadder with stepSize ' + stepSize + ' length ' + l);
      return leadingZeroPadder(n, l);
    } else {
      // console.log('  Formatter calling generic padder');
      // return simplePadder(n);
      return simpleCleaner(n);
    }
  }

export function fnHandleNumChange(props) {
  return (valueAsNumber: number, valueAsString?: string, input?: any) => {
    // console.log('== Handling number change in fnHandleNumChange');
    // onChange for this component does not match the standard, so "standardize" it
    // further enforce min/max clamping

    let formattingLengthDiff = 0;
    let m;
    if ((m = RE_LEADING_ZERO_NUM.exec(valueAsString)) !== null) {
        m.forEach((match, groupIndex) => {
            if (groupIndex == 7) { // match with leading zeros
              if (match != undefined) {
                formattingLengthDiff = match.length;
              }
            }
        });
    }

    // deal with re-rendering insertions in fnCalcPrecision
    // if (formattingLengthDiff > 0) {
    //   input.selectionStart -= formattingLengthDiff + 1; // inserted char: length 1
    //   input.selectionEnd -= formattingLengthDiff + 1;
    //   // console.log('   detected a non-rerender formatting change in fnHandleNumChange causing a cursor shift of -' + formattingLengthDiff + ' places from ' + valueAsString + ' to ' + valueAsNumber);
    //   // BUG: this will not move the cursor without changing where the number is inserted!
    // } else {
    //   // console.log('   no non-render formatting change in fnHandleNumChange');
    // }

    let decLast = valueAsString !== undefined ? (valueAsString.length - 1 == valueAsString.indexOf('.')) : false;
    let isMinus = (valueAsString === '-');

    if (!isMinus && !decLast) { // deal with special case that would result in `null` passed to onChange
      if (props.min !== undefined) {
        if (valueAsNumber < props.min) {
          valueAsNumber = props.min;
          props.gui_alert('Value of ' + props.fullname + ' cannot go below ' + props.min + '.');
        }
      }

      if (props.max !== undefined) {
        if (valueAsNumber > props.max) {
          valueAsNumber = props.max;
          props.gui_alert('Value of ' + props.fullname + ' cannot exceed ' + props.max + '.');
        }
      }
      
      let event = {
        target: {
          value: valueAsNumber
        }
      }
      props.onChange(event);
    }
  }
}

export function fnKeyDown(props, numChangeHandler) {
  return (event) => {
    // console.log('== Handling key-down event in fnKeyDown');
    let baseStep = (props.step == null) ? 1 : props.step
    let pgup = (event.key == "PageUp");
    let pgdown = (event.key == "PageDown");
    let home = (event.key == "Home");
    let end = (event.key == "End");
    let enter = (event.key == "Enter")

    if (enter) {
      event.preventDefault();
      props.onBlur();
    }
    else if (pgup) {
      if (props.max !== undefined && !isNaN(props.max)) {
        event.preventDefault();
        numChangeHandler(Math.min(props.value + 100*baseStep, props.max));
      } else {
        event.preventDefault();
        numChangeHandler(props.value + 100*baseStep);
      }
    } else if (pgdown) {
      if (props.min !== undefined && !isNaN(props.min)) {
        event.preventDefault();
        numChangeHandler(Math.max(props.value - 100*baseStep, props.min));
      } else {
        event.preventDefault();
        numChangeHandler(props.value - 100*baseStep);
      }
    } else if (home && props.min !== undefined && !isNaN(props.min)) {
      event.preventDefault();
      numChangeHandler(props.min);
    } else if (end && props.max !== undefined && !isNaN(props.max)) {
      event.preventDefault();
      numChangeHandler(props.max);
    }
    //  else if (event.key == '-' && props.min !== undefined && !isNaN(props.min) && event.target.selectionStart == 0) {
    //   if (parseFloat('-' + event.target.value) < props.min) {
    //     event.preventDefault();
    //     numChangeHandler(props.min);
    //   }
    // }
  }
}

// export function fnParse(x: string): number
// {
//     x = String(x);
//     // let decLast = (x.length - 1 == x.indexOf('.'))
//     let isMinus = (x == '-')
//     let n = parseFloat(x);
//     // if (isMinus) {
//     //   n = -0
//     // }
//     // console.log('Value parsed to ' + n)
//     return n;
// }