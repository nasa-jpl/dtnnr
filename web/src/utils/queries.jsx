import { useInfiniteQuery, useMutation, useQuery } from '@tanstack/react-query';
import { queryClient } from '../App';
import { getCookie } from './util';

export const backendQuery = (queryKey, url) => ({
  queryKey: queryKey,
  queryFn: async () => {
    const response = await fetch(url);
    let result;
    try {
      result = await response.json();
    } catch (_error) {
      throw new Error(
        'Unable to parse response from backend. The backend is likely down.',
      );
    }
    if (!response.ok) {
      console.log(result);
      throw result;
    }
    return result;
  },
});

// This isn't very efficient because the queryKey has to be unique.
// Other queries which call the same backend endpoint won't be populated from
// this fetch.
// And changing query parameters would also require refetching everything.
export const getAllQuery = (queryKey, url) => ({
  queryKey: queryKey,
  queryFn: async () => {
    let results = { items: [] };
    let next_page_token;
    do {
      let response = await fetch(
        `${url}?max_page_size=${MAX_PAGE_SIZE}${
          next_page_token !== undefined ? `&page_token=${next_page_token}` : ''
        }`,
      );
      let result;
      try {
        result = await response.json();
      } catch (_error) {
        throw new Error(
          'Unable to parse response from backend. The backend is likely down.',
        );
      }
      if (!response.ok) {
        console.log(result);
        throw result;
      }
      results.items.push(...result.items);
      next_page_token = result.next_page_token;
    } while (next_page_token !== undefined);
    return results;
  },
});

// Authentication mutations
const authnMutation = (URL) =>
  useMutation({
    mutationFn: async (values) => {
      let response = await fetch(URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(values),
      });
      let result;
      try {
        result = await response.json();
      } catch (_error) {
        throw new Error(
          'Unable to parse response from backend. The backend is likely down.',
        );
      }
      if (!response.ok) {
        console.log(result);
        throw result;
      }
      return result;
    },
    throwOnError: (error) => error.response?.status >= 500,
  });

export const useRegisterMutation = () => authnMutation(`/auth/register`);
export const useLogInMutation = () => authnMutation(`/auth/login`);
export const useLogoutMutation = () => authnMutation(`/auth/logout`);

// We need to define these as objects to be passed to useQuery() rather than
// the object returned from useQuery() because queryClient.prefetchQuery()
// takes { queryKey, queryFn }, not the result from useQuery()

const MAX_PAGE_SIZE = 1000;

export const MAX_PHONE_NUMBERS = 1000;

// TODO: this probably shouldn't exist anymore
// export const generalTableQuery = backendQuery(
//   ['nodes', 'general'],
//   `/api/v1/nodes/general`,
// );
export const allocatorTableQuery = getAllQuery(
  ['allocators'],
  `/api/allocators`,
);
export const operatorTableQuery = getAllQuery(['operators'], `/api/operators`);
export const hostTableQuery = getAllQuery(['hosts'], `/api/hosts`);
export const nodeTableQuery = getAllQuery(['nodes'], `/api/nodes`);

// *Id comes from the path URL, so it should be a String. Pass the String here
// rather than Number(*_id) because, e.g., we don't want /allocators/1e0 to
// make an API call to /api/allocators/1
export const contactDetailsQuery = (contactId) =>
  backendQuery(['contacts', contactId], `/api/contacts/${contactId}`);

export const allocatorDetailsQuery = (allocatorId) =>
  backendQuery(['allocators', allocatorId], `/api/allocators/${allocatorId}`);

export const operatorDetailsQuery = (operatorId) =>
  backendQuery(['operators', operatorId], `/api/operators/${operatorId}`);

export const hostDetailsQuery = (hostId) =>
  backendQuery(['hosts', hostId], `/api/hosts/${hostId}`);

export const nodeDetailsQuery = (nodeId) =>
  backendQuery(['nodes', nodeId], `/api/nodes/${nodeId}`);

const backendDeleteMutation = (
  URL,
  fieldIdName,
  queriesToInvalidate,
  setupInvalidateForeignQueries,
) =>
  useMutation({
    // We need to pass in the record and not just the surrogate key because
    // onSuccess needs to know associated objects to invalidate to use
    // setupInvalidateForeignQueries
    mutationFn: async (record) => {
      let response = await fetch(`${URL}${record[fieldIdName]}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-XSRF-TOKEN': getCookie('XSRF-TOKEN'),
        },
      });
      // 204 doesn't return anything, so we expect .json() to fail
      if (!response.ok) {
        let result;
        try {
          result = await response.json();
        } catch (_error) {
          throw new Error(
            'Unable to parse response from backend. The backend is likely down.',
          );
        }
        console.log(result);
        throw result;
      }
      return;
    },
    onSuccess: (_data, variables, _context) => {
      let queries = queriesToInvalidate;
      if (setupInvalidateForeignQueries !== undefined) {
        queries = queries.concat(setupInvalidateForeignQueries(variables));
      }
      queries.forEach((q) => {
        queryClient.invalidateQueries(q);
      });
    },
    throwOnError: (error) => error.response?.status >= 500,
  });

/**
 * Mutation for performing a POST request to backend.
 *
 * @param {string} URL URL to fetch from
 * @param {Array} queriesToInvalidate array of query keys to invalidate on success
 * @param {function} createQueryKeyToSetDataFor function that receives the repsonse
 * body as an argument and returns a query key
 * @returns a mutation
 */
const backendPostMutation = (
  URL,
  queriesToInvalidate,
  createQueryKeyToSetDataFor,
) =>
  useMutation({
    // Assume `values` is of the form
    // {
    //   body: { ... },
    //   searchParams: URLSearchParams | undefined
    // }
    // Otherwise, `values` will be used as the request body
    mutationFn: async (values) => {
      let response = await fetch(
        `${URL}?${values.searchParams === undefined ? '' : values.searchParams}`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-XSRF-TOKEN': getCookie('XSRF-TOKEN'),
          },
          body: JSON.stringify(values.body ?? values),
        },
      );
      if (response.status === 204) {
        return null;
      }
      let result;
      try {
        result = await response.json();
      } catch (_error) {
        throw new Error(
          'Unable to parse response from backend. The backend is likely down.',
        );
      }
      if (!response.ok) {
        console.log(result);
        throw result;
      }
      return result;
    },
    onSuccess: (data, _variables, _context) => {
      queriesToInvalidate.forEach((q) => {
        queryClient.invalidateQueries(q);
      });
      if (createQueryKeyToSetDataFor !== undefined) {
        queryClient.setQueryData(createQueryKeyToSetDataFor(data), data);
      }
    },
    throwOnError: (error) => error.response?.status >= 500,
  });

/**
 * Mutation for performing a PATCH request to backend.
 *
 * @param {string} URL URL to fetch from
 * @param {Array} queriesToInvalidate array of query keys to invalidate on success
 * @param {function} setupInvalidateForeignQueries function that returns an array
 * of query keys that will be invalidated along with `queriesToInvalidate`.
 * Receives the response body as its arugment.
 * @param {function} createQueryKeyToSetDataFor function that receives the response
 * body as an argument and returns a query key
 * @returns a mutation
 */
const backendPatchMutation = (
  URL,
  queriesToInvalidate,
  setupInvalidateForeignQueries,
  createQueryKeyToSetDataFor,
) =>
  useMutation({
    // Assume `values` is of the form
    // {
    //   body: { ... },
    //   searchParams: URLSearchParams | undefined
    // }
    // Otherwise, `values` will be used as the request body
    mutationFn: async (values) => {
      let response = await fetch(
        `${URL}?${values.searchParams === undefined ? '' : values.searchParams}`,
        {
          method: 'PATCH',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-XSRF-TOKEN': getCookie('XSRF-TOKEN'),
          },
          body: JSON.stringify(values.body ?? values),
        },
      );
      if (response.status === 204) {
        return null;
      }
      let result;
      try {
        result = await response.json();
      } catch (_error) {
        throw new Error(
          'Unable to parse response from backend. The backend is likely down.',
        );
      }
      if (!response.ok) {
        console.log(result);
        throw result;
      }
      return result;
    },
    onSuccess: (data, _variables, _context) => {
      if (createQueryKeyToSetDataFor !== undefined) {
        queryClient.setQueryData(createQueryKeyToSetDataFor(data), data);
      }
      let queries = queriesToInvalidate;
      if (setupInvalidateForeignQueries !== undefined) {
        queries = queries.concat(setupInvalidateForeignQueries(data));
      }
      queries.forEach((q) => {
        queryClient.invalidateQueries(q);
      });
    },
    throwOnError: (error) => error.response?.status >= 500,
  });

/**
 * Mutation for performing a PUT request to backend.
 *
 * @param {string} URL URL to fetch from
 * @param {Array} queriesToInvalidate array of query keys to invalidate on success
 * @param {function} setupInvalidateForeignQueries function that returns an array
 * of query keys that will be invalidated along with `queriesToInvalidate`.
 * Receives the response body as its arugment.
 * @param {function} createQueryKeyToSetDataFor function that receives the response
 * body as an argument and returns a query key
 * @returns a mutation
 */
const backendPutMutation = (
  URL,
  queriesToInvalidate,
  setupInvalidateForeignQueries,
  createQueryKeyToSetDataFor,
) =>
  useMutation({
    // Assume `values` is of the form
    // {
    //   body: { ... },
    //   searchParams: URLSearchParams | undefined
    // }
    // Otherwise, `values` will be used as the request body
    mutationFn: async (values) => {
      let response = await fetch(
        `${URL}?${values.searchParams === undefined ? '' : values.searchParams}`,
        {
          method: 'PUT',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-XSRF-TOKEN': getCookie('XSRF-TOKEN'),
          },
          body: JSON.stringify(values.body ?? values),
        },
      );
      if (response.status === 204) {
        return null;
      }
      let result;
      try {
        result = await response.json();
      } catch (_error) {
        console.log(_error);
        throw new Error(
          'Unable to parse response from backend. The backend is likely down.',
        );
      }
      if (!response.ok) {
        console.log(result);
        throw result;
      }
      return result;
    },
    onSuccess: (data, _variables, _context) => {
      if (createQueryKeyToSetDataFor !== undefined) {
        queryClient.setQueryData(createQueryKeyToSetDataFor(data), data);
      }
      let queries = queriesToInvalidate;
      if (setupInvalidateForeignQueries !== undefined) {
        queries = queries.concat(setupInvalidateForeignQueries(data));
      }
      queries.forEach((q) => {
        queryClient.invalidateQueries(q);
      });
    },
    throwOnError: (error) => error.response?.status >= 500,
  });

// Contact
const queriesToInvalidateOnAssociateAllocatorContact = (allocatorId) => [
  { queryKey: ['allocators'], exact: true },
  { queryKey: ['allocators', allocatorId, 'contacts'] },
];

const queriesToInvalidateOnAssociateOperatorContact = (operatorId) => [
  { queryKey: ['operators'], exact: true },
  { queryKey: ['operators', operatorId, 'contacts'] },
];

const queriesToInvalidateOnAssociateHostContact = (hostId) => [
  { queryKey: ['hosts'], exact: true },
  { queryKey: ['hosts', hostId, 'contacts'] },
];

const queriesToInvalidateOnAssociateNodeContact = (nodeId) => [
  { queryKey: ['nodes'], exact: true },
  // To refresh modified_at time
  { queryKey: ['nodes', nodeId], exact: true },
  { queryKey: ['nodes', nodeId, 'contacts'] },
];

// TODO: we used to include number of contacts for each main entity's table,
// but we don't do that anymore.
const queriesToInvalidateOnDissociateContact = [
  // { queryKey: ['allocators'], exact: true },
  // { queryKey: ['operators'], exact: true },
  // { queryKey: ['hosts'], exact: true },
  // { queryKey: ['nodes'], exact: true },
];

// TODO: this only invalidates the parent entity's contacts query rather than
// every parents' contacts queries. This is *okay* for now since we don't have
// a page with multiple parents' contact queries. It's logically correct for
// all of those queries to be invalidated, but figuring out all of the contact's
// allocators, operators, hosts, and nodes is a pain since our API doesn't have
// that in the response of a contact anymore.
const setupInvalidateForeignQueriesContact =
  (parentEntity, parentID) => (contact) => [
    { queryKey: ['contacts', contact.contact_id], exact: true },
    { queryKey: [parentEntity, parentID, 'contacts'] },
  ];
// .concat(
//   [... contact.allocators.map((a) => a.allocator_id)].map((aId) => ({ queryKey: ['allocators', aId, 'contacts'] }))
// ).concat(
//   [... contact.operators.map((o) => o.operator_id)].map((oId) => ({ queryKey: ['operators', oId, 'contacts'] }))
// ).concat(
//   [... contact.hosts.map((h) => h.host_id)].map((hId) => ({ queryKey: ['hosts', hId, 'contacts'] }))
// ).concat(
//   [... contact.nodes.map((n) => n.node_id)].map((nId) => ({ queryKey: ['nodes', nId, 'contacts'] }))
// );

export const useUpdateContactMutation = (contactId) =>
  backendPatchMutation(
    `/api/contacts/${contactId}`,
    [{ queryKey: ['contacts'], exact: true }],
    // TODO: should really invalidate all /*/*/contacts of parents, but don't
    // know how to go about it, so doing undefined for now
    undefined,
    (data) => ['contacts', data.contact_id],
  );

export const useDeleteContactMutation = () =>
  backendDeleteMutation(
    `/api/contacts/`,
    'contact_id',
    [{ queryKey: ['contacts'], exact: true }],
    // TODO: same reason as useUpdateContactMutation, use undefined for now
    undefined,
  );

export const usePhoneNumberAllQuery = (contactId) =>
  useQuery({
    ...getAllQuery(
      ['contacts', contactId, 'phone-numbers'],
      `/api/contacts/${contactId}/phone-numbers`,
    ),
    // Without an ID, doing list renders is annoying, and seems nicer to
    // have this as part of the query.
    select: (data) => ({
      items: data.items.map((item, index) => ({
        ...item,
        id: `${item.phone_number}-${index}`,
      })),
    }),
  });

export const useReplacePhoneNumberMutation = (contactId) =>
  backendPutMutation(`/api/contacts/${contactId}/phone-numbers`, [
    'contacts',
    contactId,
    'phone-numbers',
  ]);

// Allocator
const queriesToInvalidateOnCreateAllocator = [
  { queryKey: ['allocators'], exact: true },
];

// Updating could change the ID / name. We display the ID on the operator
// and node table.
// Deleting an allocator deletes all of its operators and nodes, so we should
// also invalidate the same queries.
const queriesToInvalidateOnUpdateAllocator =
  queriesToInvalidateOnCreateAllocator.concat([
    { queryKey: ['operators'], exact: true },
    { queryKey: ['nodes'], exact: true },
  ]);

// For updating / deleting, we need to invalidate the operators and nodes that
// belong to the allocator.
const setupInvalidateForeignQueriesAllocator = (allocator) =>
  [...allocator.operators.map((o) => o.operator_id)]
    .map((oId) => ({ queryKey: ['operators', oId], exact: true }))
    .concat(
      [...allocator.nodes.map((n) => n.node_id)].map((nodeId) => ({
        queryKey: ['nodes', nodeId],
        exact: true,
      })),
    );
// TODO: I don't like this. If you want to invalidate stuff, you should pass
// a separate collection for operators / nodes.
// These are queries for individual resources and they _should_ be invalidated,
// I just don't have an endpoint at the moment to efficiently retrieve operators
// and nodes.

export const useCreateAllocatorMutation = () =>
  backendPostMutation(
    `/api/allocators`,
    queriesToInvalidateOnCreateAllocator,
    (data) => ['allocators', data.allocator_id],
  );

export const useUpdateAllocatorMutation = (allocatorId) =>
  backendPatchMutation(
    `/api/allocators/${allocatorId}`,
    queriesToInvalidateOnUpdateAllocator,
    setupInvalidateForeignQueriesAllocator, // TODO: change to () => []
    (data) => ['allocators', data.allocator_id],
  );

export const useDeleteAllocatorMutation = (allocatorId) =>
  backendDeleteMutation(
    `/api/allocators/`,
    'allocator_id',
    queriesToInvalidateOnUpdateAllocator.concat({
      queryKey: ['allocators', allocatorId],
      exact: true,
    }),
    setupInvalidateForeignQueriesAllocator,
  );

export const allocatorContactQuery = (allocatorId) =>
  getAllQuery(
    ['allocators', allocatorId, 'contacts'],
    `/api/allocators/${allocatorId}/contacts`,
  );

export const useAssociateAllocatorContactMutation = (allocatorId) =>
  backendPostMutation(
    `/api/allocators/${allocatorId}/contacts`,
    queriesToInvalidateOnAssociateAllocatorContact(allocatorId),
    (data) => ['contacts', data.contact_id],
  );

export const useDissociateAllocatorContactMutation = (allocatorId) =>
  backendDeleteMutation(
    `/api/allocators/${allocatorId}/contacts/`,
    'contact_id',
    queriesToInvalidateOnDissociateContact,
    setupInvalidateForeignQueriesContact('allocators', allocatorId),
  );

// Operator
const queriesToInvalidateOnCreateOperator = [
  { queryKey: ['operators'], exact: true },
  { queryKey: ['allocators'], exact: true },
];

// Updating could change the operator's allocator or name.
// This can affect ['operators'] and ['allocators']
// Operator name is shown on host and node tables
// Deleting an operator also deletes related hosts and nodes
const queriesToInvalidateOnUpdateOperator =
  queriesToInvalidateOnCreateOperator.concat([
    { queryKey: ['hosts'], exact: true },
    { queryKey: ['nodes'], exact: true },
  ]);

// Operator name is shown on specific allocator, host, and node pages
const setupInvalidateForeignQueriesOperator = (operator) =>
  [{ queryKey: ['allocators', operator.allocator.allocator_id], exact: true }]
    .concat([
      ...operator.hosts.map((h) => ({
        queryKey: ['hosts', h.host_id],
        exact: true,
      })),
    ])
    .concat([
      ...operator.nodes.map((n) => ({
        queryKey: ['nodes', n.node_id],
        exact: true,
      })),
    ]);
// TODO: new API will not include hosts and nodes in operators' representation

export const useCreateOperatorMutation = () =>
  backendPostMutation(
    `/api/operators`,
    queriesToInvalidateOnCreateOperator,
    (data) => ['operators', data.operator_id],
  );

export const useUpdateOperatorMutation = (operatorId) =>
  backendPatchMutation(
    `/api/operators/${operatorId}`,
    queriesToInvalidateOnUpdateOperator,
    setupInvalidateForeignQueriesOperator,
    (data) => ['operators', data.operator_id],
  );

export const useUpdateAllocatedNodeNumbersMutation = (operatorId) =>
  backendPostMutation(
    `/api/operators/${operatorId}/allocated-node-numbers`,
    // We currently only display allocated node numbers on the operators table
    // and operator's details page
    [{ queryKey: ['operators'], exact: true }],
    (data) => ['operators', data.operator_id],
  );

export const useDeleteOperatorMutation = (operatorId) =>
  backendDeleteMutation(
    `/api/operators/`,
    'operator_id',
    queriesToInvalidateOnUpdateOperator.concat({
      queryKey: ['operators', operatorId],
      exact: true,
    }),
    setupInvalidateForeignQueriesOperator,
  );

export const operatorContactQuery = (operatorId) =>
  // operatorId should be a Number, so no need to cast
  getAllQuery(
    ['operators', operatorId, 'contacts'],
    `/api/operators/${operatorId}/contacts`,
  );

export const useAssociateOperatorContactMutation = (operatorId) =>
  backendPostMutation(
    `/api/operators/${operatorId}/contacts`,
    queriesToInvalidateOnAssociateOperatorContact(operatorId),
    (data) => ['contacts', data.contact_id],
  );

export const useDissociateOperatorContactMutation = (operatorId) =>
  backendDeleteMutation(
    `/api/operators/${operatorId}/contacts/`,
    'contact_id',
    queriesToInvalidateOnDissociateContact,
    setupInvalidateForeignQueriesContact('operators', operatorId),
  );

// Host
const queriesToInvalidateOnCreateHost = [
  { queryKey: ['hosts'], exact: true },
  { queryKey: ['operators'], exact: true },
];

// Operators table only shows the number of hosts, so we don't need to
// invalidate that when updating
const queriesToInvalidateOnUpdateHost = [
  { queryKey: ['hosts'], exact: true },
  // { queryKey: ['hosts', hostId], exact: true },
  { queryKey: ['nodes'], exact: true },
];

// Invalidate operators (shows number of hosts), nodes (will be deleted),
// allocators (number of nodes will change)
const queriesToInvalidateOnDeleteHost = [
  { queryKey: ['hosts'], exact: true },
  { queryKey: ['allocators'], exact: true },
  { queryKey: ['operators'], exact: true },
  { queryKey: ['nodes'], exact: true },
];

// Invalidate related operators and nodes (they display name of host names)
const setupInvalidateForeignQueriesHost = (host) => {
  // TODO: new API will not have nodes in host's representation
  let arr = [...new Set(host.nodes.flatMap((n) => n.node_id))].map((id) => ({
    queryKey: ['nodes', id],
    exact: true,
  }));
  if (host?.operator?.operator_id !== undefined) {
    arr = arr.concat({
      queryKey: ['operators', host?.operator?.operator_id],
      exact: true,
    });
  }
  return arr;
};

export const useCreateHostMutation = () =>
  backendPostMutation(`/api/hosts`, queriesToInvalidateOnCreateHost, (data) => [
    'hosts',
    data.host_id,
  ]);

export const useUpdateHostMutation = (hostId) =>
  backendPatchMutation(
    `/api/hosts/${hostId}`,
    queriesToInvalidateOnUpdateHost,
    setupInvalidateForeignQueriesHost,
    (data) => ['hosts', data.host_id],
  );

export const useDeleteHostMutation = () =>
  backendDeleteMutation(
    `/api/hosts/`,
    'host_id',
    queriesToInvalidateOnDeleteHost,
    setupInvalidateForeignQueriesHost,
  );

export const useCopyHostMutation = (hostId) =>
  backendPostMutation(
    `/api/hosts/${hostId}/copies`,
    // We usually copy hosts with nodes, and queriesToInvalidateNode includes
    // everything that queriesToInvalidateOnCreateHost, so we can use that
    // instead.
    queriesToInvalidateNode,
    (data) => ['hosts', data.host_id],
  );

export const hostContactQuery = (hostId) =>
  getAllQuery(['hosts', hostId, 'contacts'], `/api/hosts/${hostId}/contacts`);

export const useAssociateHostContactMutation = (hostId) =>
  backendPostMutation(
    `/api/hosts/${hostId}/contacts`,
    queriesToInvalidateOnAssociateHostContact(hostId),
    (data) => ['contacts', data.contact_id],
  );

export const useDissociateHostContactMutation = (hostId) =>
  backendDeleteMutation(
    `/api/hosts/${hostId}/contacts/`,
    'contact_id',
    queriesToInvalidateOnDissociateContact,
    setupInvalidateForeignQueriesContact('hosts', hostId),
  );

// Node
const queriesToInvalidateNode = [
  { queryKey: ['nodes'], exact: true },
  // { queryKey: ['nodes', 'general'], exact: true },
  { queryKey: ['allocators'], exact: true },
  { queryKey: ['operators'], exact: true },
  { queryKey: ['hosts'], exact: true },
];

const setupInvalidateForeignQueriesNode = (node) => [
  { queryKey: ['allocators', node.allocator.allocator_id], exact: true },
  ...(node.host
    ? [{ queryKey: ['hosts', node.host.host_id], exact: true }]
    : []),
  ...(node.operator
    ? [{ queryKey: ['operators', node.operator.operator_id], exact: true }]
    : []),
];

export const useCreateNodeMutation = () =>
  backendPostMutation(`/api/nodes`, queriesToInvalidateNode, (data) => [
    'nodes',
    data.node_id,
  ]);

export const useUpdateNodeMutation = (nodeId) =>
  backendPatchMutation(
    `/api/nodes/${nodeId}`,
    queriesToInvalidateNode.concat([{ queryKey: ['nodes', nodeId] }]),
    setupInvalidateForeignQueriesNode,
    (data) => ['nodes', data.node_id],
  );

export const useDeleteNodeMutation = () =>
  backendDeleteMutation(
    `/api/nodes/`,
    'node_id',
    queriesToInvalidateNode,
    setupInvalidateForeignQueriesNode,
  );

export const useCopyNodeMutation = (nodeId) =>
  backendPostMutation(
    `/api/nodes/${nodeId}/copies`,
    queriesToInvalidateNode,
    (data) => ['nodes', data.node_id],
  );

export const nodeContactQuery = (nodeId) =>
  getAllQuery(['nodes', nodeId, 'contacts'], `/api/nodes/${nodeId}/contacts`);

export const useAssociateNodeContactMutation = (nodeId) =>
  backendPostMutation(
    `/api/nodes/${nodeId}/contacts`,
    queriesToInvalidateOnAssociateNodeContact(nodeId),
    (data) => ['contacts', data.contact_id],
  );

export const useDissociateNodeContactMutation = (nodeId) =>
  backendDeleteMutation(
    `/api/nodes/${nodeId}/contacts/`,
    'contact_id',
    queriesToInvalidateOnDissociateContact.concat([
      { queryKey: ['nodes', nodeId], exact: true },
    ]),
    setupInvalidateForeignQueriesContact,
  );

// Destination table

const queriesToInvalidateOnCreateDestination = (hostId) => [
  { queryKey: ['hosts', hostId, 'destinations'] },
];

// TODO: this was used when our IP address resource had an array of inducts.
// We don't have that anymore. Eventually, we should be able to filter for nodes
// with seats or inducts referencing a particular destination.
// const setupInvalidateForeignQueriesIpAddress = (ip) =>
//   [
//     ...new Set(ip.ip_inducts.map((ip_i) => ip_i.induct.node.node_id).flat()),
//   ].map((nodeId) => ({ queryKey: ['nodes', nodeId, 'inducts'] }));

export const useDestinationQuery = (hostId) =>
  useQuery(
    getAllQuery(
      ['hosts', hostId, 'destinations'],
      `/api/hosts/${hostId}/destinations`,
    ),
  );

export const useCreateDestinationMutation = (hostId) =>
  backendPostMutation(
    `/api/hosts/${hostId}/destinations`,
    queriesToInvalidateOnCreateDestination(hostId),
  );

export const useUpdateDestinationMutation = (destinationId, hostId) =>
  backendPatchMutation(
    `/api/destinations/${destinationId}`,
    queriesToInvalidateOnCreateDestination(hostId),
    // setupInvalidateForeignQueriesIpAddress,
  );

export const useDeleteDestinationMutation = (hostId) =>
  backendDeleteMutation(
    `/api/destinations/`,
    'destination_id',
    queriesToInvalidateOnCreateDestination(hostId),
    // setupInvalidateForeignQueriesIpAddress,
  );

// Link table

const queriesToInvalidateOnCreateLink = (hostId) => [
  { queryKey: ['hosts', hostId, 'links'] },
];

export const useLinkQuery = (hostId) =>
  useQuery(
    getAllQuery(['hosts', hostId, 'links'], `/api/hosts/${hostId}/links`),
  );

export const useCreateLinkMutation = (hostId) =>
  backendPostMutation(
    `/api/hosts/${hostId}/links`,
    queriesToInvalidateOnCreateLink(hostId),
  );

export const useUpdateLinkMutation = (linkId, hostId) =>
  backendPatchMutation(
    `/api/links/${linkId}`,
    queriesToInvalidateOnCreateLink(hostId),
    // TODO: ideally you'd invalidate each /inducts/{induct_id}/links and
    // /seats/{seat_id}/links query. Not really an easy way to do this;
    // should consider adding an endpoint like /links/{link_id}/inducts and
    // /links/{link_id}/seats. Then again, the invalidation only matters if
    // user has components showing an induct's links or seat's links while
    // updating the link which is unlikely.
  );

export const useDeleteLinkMutation = (hostId) =>
  backendDeleteMutation(
    `/api/links/`,
    'link_id',
    queriesToInvalidateOnCreateLink(hostId),
    // TOOD: same point above about updating links
  );

// EndpointIpn table

// Invalidate these queries when we create / edit an ipn endpoint
const queriesToInvalidateEndpointIpn = (nodeId) => [
  { queryKey: ['nodes', nodeId, 'ipn-endpoints'] },
  // Refresh the parent node since updated_at changed
  { queryKey: ['nodes', nodeId], exact: true },
];

export const useCreateEndpointIpnMutation = (nodeId) =>
  backendPostMutation(
    `/api/nodes/${nodeId}/endpoints/ipn`,
    queriesToInvalidateEndpointIpn(nodeId),
  );

export const useUpdateEndpointIpnMutation = (nodeId, serviceNumber) =>
  backendPatchMutation(
    `/api/nodes/${nodeId}/endpoints/ipn/${serviceNumber}`,
    queriesToInvalidateEndpointIpn(nodeId),
  );

export const useDeleteEndpointIpnMutation = (nodeId) =>
  backendDeleteMutation(
    `/api/nodes/${nodeId}/endpoints/ipn/`,
    'service_number',
    queriesToInvalidateEndpointIpn(nodeId),
  );

// EndpointImc table

// Invalidate these queries when we create / edit an imc endpoint
const queriesToInvalidateEndpointImc = (nodeId) => [
  { queryKey: ['nodes', nodeId, 'imc-endpoints'] },
  { queryKey: ['nodes', nodeId], exact: true },
];

export const useCreateEndpointImcMutation = (nodeId) =>
  backendPostMutation(
    `/api/nodes/${nodeId}/endpoints/imc`,
    queriesToInvalidateEndpointImc(nodeId),
  );

export const useUpdateEndpointImcMutation = (nodeId, groupNumber) =>
  backendPatchMutation(
    `/api/nodes/${nodeId}/endpoints/imc/${groupNumber}`,
    queriesToInvalidateEndpointImc(nodeId),
  );

export const useDeleteEndpointImcMutation = (nodeId) =>
  backendDeleteMutation(
    `/api/nodes/${nodeId}/endpoints/imc/`,
    'group_number',
    queriesToInvalidateEndpointImc(nodeId),
  );

// CL protocol table

const queriesToInvalidateOnCreateClProtocol = (nodeId) => [
  { queryKey: ['nodes', nodeId, 'cl-protocols'] },
  { queryKey: ['nodes', nodeId], exact: true },
];

// Queries to invalidate when updating / deleting
export const queriesToInvalidateOnEditClProtocol = (nodeId) =>
  queriesToInvalidateOnCreateClProtocol(nodeId).concat([
    { queryKey: ['nodes', nodeId, 'inducts'] },
  ]);

export const useClProtocolQuery = (nodeId) =>
  useQuery(
    getAllQuery(
      ['nodes', nodeId, 'cl-protocols'],
      `/api/nodes/${nodeId}/cl-protocols`,
    ),
  );

export const useCreateClProtocolMutation = (nodeId) =>
  backendPostMutation(
    `/api/nodes/${nodeId}/cl-protocols`,
    queriesToInvalidateOnCreateClProtocol(nodeId),
  );

export const useUpdateClProtocolMutation = (clProtocolId, nodeId) =>
  backendPatchMutation(
    `/api/cl-protocols/${clProtocolId}`,
    queriesToInvalidateOnEditClProtocol(nodeId),
  );

export const useDeleteClProtocolMutation = (nodeId) =>
  backendDeleteMutation(
    `/api/cl-protocols/`,
    'cl_protocol_id',
    queriesToInvalidateOnEditClProtocol(nodeId),
  );

// Induct table

// For creating / editing an induct
const queriesToInvalidateInduct = (nodeId) => [
  { queryKey: ['nodes', nodeId, 'inducts'] },
  { queryKey: ['nodes', nodeId], exact: true },
];

export const useInductQuery = (nodeId) =>
  useQuery(
    getAllQuery(['nodes', nodeId, 'inducts'], `/api/nodes/${nodeId}/inducts`),
  );

export const useCreateInductMutation = (nodeId) =>
  backendPostMutation(
    `/api/nodes/${nodeId}/inducts`,
    queriesToInvalidateInduct(nodeId),
  );

export const useReplaceInductMutation = (inductId, nodeId) =>
  backendPutMutation(
    `/api/inducts/${inductId}`,
    queriesToInvalidateInduct(nodeId),
  );

export const useDeleteInductMutation = (nodeId) =>
  backendDeleteMutation(
    `/api/inducts/`,
    'induct_id',
    queriesToInvalidateInduct(nodeId),
    (induct) => [
      { queryKey: ['inducts', induct.induct_id, 'links'] },
      { queryKey: ['inducts', induct.induct_id, 'seats'] },
    ],
  );

async function fetchPage(url, pageParam, pageSize) {
  const params = new URLSearchParams({
    ...(pageParam !== undefined && { page_token: pageParam }),
    ...(pageSize !== undefined && { max_page_size: pageSize }),
  });
  const response = await fetch(`${url}?${params}`);
  let result;
  try {
    result = await response.json();
  } catch (_error) {
    throw new Error(
      'Unable to parse response from backend. The backend is likely down.',
    );
  }
  if (!response.ok) {
    throw result;
  }
  return result;
}

export const useInductLinkQuery = (inductId) =>
  useInfiniteQuery({
    queryKey: ['inducts', inductId, 'links'],
    queryFn: ({ pageParam }) =>
      fetchPage(`/api/inducts/${inductId}/links`, pageParam),
    initialPageParam: undefined,
    getNextPageParam: (lastPage) => lastPage.next_page_token,
  });

export const useInductLinkAllQuery = (inductId) =>
  useQuery(
    getAllQuery(
      ['inducts', inductId, 'links', 'all'],
      `/api/inducts/${inductId}/links`,
    ),
  );

export const useReplaceInductLinkMutation = (inductId) =>
  backendPutMutation(`/api/inducts/${inductId}/links`, [
    'inducts',
    inductId,
    'links',
  ]);

export const useInductSeatQuery = (inductId) =>
  useInfiniteQuery({
    queryKey: ['inducts', inductId, 'seats'],
    queryFn: ({ pageParam }) =>
      fetchPage(`/api/inducts/${inductId}/seats`, pageParam),
    initialPageParam: undefined,
    getNextPageParam: (lastPage) => lastPage.next_page_token,
  });

export const useInductSeatAllQuery = (inductId) =>
  useQuery(
    getAllQuery(
      ['inducts', inductId, 'seats', 'all'],
      `/api/inducts/${inductId}/seats`,
    ),
  );

export const useReplaceInductSeatMutation = (inductId) =>
  backendPutMutation(`/api/inducts/${inductId}/seats`, [
    'inducts',
    inductId,
    'seats',
  ]);

// Seat table

// For creating / editing a seat
const queriesToInvalidateSeat = (nodeId) => [
  { queryKey: ['nodes', nodeId, 'seats'] },
  { queryKey: ['nodes', nodeId], exact: true },
];

export const useSeatQuery = (nodeId) =>
  useQuery(
    getAllQuery(['nodes', nodeId, 'seats'], `/api/nodes/${nodeId}/seats`),
  );

export const useCreateSeatMutation = (nodeId) =>
  backendPostMutation(
    `/api/nodes/${nodeId}/seats`,
    queriesToInvalidateSeat(nodeId),
  );

export const useReplaceSeatMutation = (seatId, nodeId) =>
  backendPutMutation(`/api/seats/${seatId}`, queriesToInvalidateSeat(nodeId));

export const useDeleteSeatMutation = (nodeId) =>
  backendDeleteMutation(
    `/api/seats/`,
    'seat_id',
    queriesToInvalidateSeat(nodeId),
    (seat) => [{ queryKey: ['inducts', seat.seat_id, 'links'] }],
  );

export const useSeatLinkQuery = (seatId) =>
  useInfiniteQuery({
    queryKey: ['seats', seatId, 'links'],
    queryFn: ({ pageParam }) =>
      fetchPage(`/api/seats/${seatId}/links`, pageParam),
    initialPageParam: undefined,
    getNextPageParam: (lastPage) => lastPage.next_page_token,
  });

export const useSeatLinkAllQuery = (seatId) =>
  useQuery(
    getAllQuery(
      ['seats', seatId, 'links', 'all'],
      `/api/seats/${seatId}/links`,
    ),
  );

export const useReplaceSeatLinkMutation = (seatId) =>
  backendPutMutation(`/api/seats/${seatId}/links`, ['seats', seatId, 'links']);
