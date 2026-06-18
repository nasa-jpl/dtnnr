import { parsePhoneNumber } from 'awesome-phonenumber';

export function formatTelURI(phone_number) {
  return (
    parsePhoneNumber(phone_number, { regionCode: 'US' })?.number?.rfc3966 ??
    `tel:${phone_number}`
  );
}

export function formatGeneralError(
  error,
  fallbackMessage = 'Unexpected error occurred.',
) {
  // "Validation Error" errors have a particular syntax
  if (error?.title === 'Validation Error') {
    let res = extra.map(({ key, message }) => `${key}: ${message}`);
    return res.join('\n'); // Does this even render in separate lines?
  }
  if (typeof error?.detail === 'object') {
    return JSON.stringify(error.detail);
  }
  // `detail` is for our 400 and 404 errors
  // `message` is for JavaScript errors
  // .toString() is to make sure whatever `error` is, it's rendered as a string
  return (
    error?.detail ?? error?.message ?? error?.toString() ?? fallbackMessage
  );
}

function formatDataForSelect(id, name) {
  // Using the value, label format for Mantine's Select component
  // `value` is what is sent to the backend
  // `label` is what is rendered for the current selection
  return {
    value: `${id}`,
    label: `[${id}] ${name}`,
  };
}

export function formatContact(contact) {
  return {
    value: `${contact.contact_id}`,
    label: contact.email
      ? `[${contact.contact_id}] ${contact.contact_name} (${contact.email})`
      : `[${contact.contact_id}] ${contact.contact_name}`,
  };
}

// Used in OperatorTable and Operator
export function formatAllocatedNodeNumbers(arr) {
  return arr
    .map((r) => `${r.bounds[0]}${r.lower}, ${r.upper}${r.bounds[1]}`)
    .join(' ∪ ');
}

// TODO: should probably use formatAllocator, formatOperator, formatHost where
// we use FetchSelect

// Used in OperatorForm and NodeForm
export function formatAllocator(allocator) {
  if (!allocator) {
    // Assumes the default allocator is available
    return formatDataForSelect('0', 'Default Allocator');
  }
  return formatDataForSelect(allocator.allocator_id, allocator.allocator_name);
}

// Used in NodeForm
export function formatOperator(operator) {
  if (!operator) {
    return null;
  }
  return formatDataForSelect(operator.operator_id, operator.operator_name);
}

// Used in HostForm
export function formatHost(host) {
  if (!host) {
    return null;
  }
  return formatDataForSelect(host.host_id, host.hostname);
}

export function formatUnderlyingCommService(ucs) {
  if (!ucs) {
    return null;
  }
  return formatDataForSelect(
    ucs.underlying_communication_service_id,
    ucs.underlying_communication_service_name,
  );
}

// Used in InductLinks
export function formatLinkForTable(l) {
  let arr = []; // band name, direction
  if (l?.link_rf?.band?.band_name ?? false) {
    arr.push(l.link_rf.band.band_name);
  }
  if (l?.direction ?? false) {
    arr.push(l.direction);
  }
  const csv = arr.join(', ');
  let ucs = [];
  if (l?.underlying_communication_services?.length !== 0) {
    ucs = l.underlying_communication_services.map(
      (s) => s.underlying_communication_service_name,
    );
  }
  let ucsString = '';
  if (ucs.length !== 0) {
    ucsString = ` (${ucs.join(', ')})`;
  }
  return `[${l.link_id}] ${csv}${ucsString}`;
}

export function formatLinkForForm(link) {
  if (!link) {
    return null;
  }
  return {
    value: link.link_id,
    label: formatLinkForTable(link),
  };
}

// Used in LinkForm
export function formatBand(band) {
  if (!band) {
    return null;
  }
  return formatDataForSelect(band.band_id, band.band_name);
}

// Used in InductSeats
export function formatSeat(seat) {
  if (!seat) {
    return null;
  }
  return formatDataForSelect(seat.seat_id, seat.lsi_command);
}

export function formatDestination(destination) {
  if (!destination) {
    return null;
  }
  return formatDataForSelect(
    destination.destination_id,
    destination.destination_value,
  );
}
