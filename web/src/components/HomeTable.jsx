import { rem } from '@mantine/core';
import { DataTable } from 'mantine-datatable';
import { useEffect, useState } from 'react';

// import { sortBy } from '../utils/util';

const PAGE_SIZES = [10, 25, 50, 100];

export function HomeTable({
  initialColumnAccessor,
  filteredData,
  dataIsFiltered,
  ...otherProps
}) {
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);
  const [page, setPage] = useState(1);
  const [records, setRecords] = useState([]);
  const [numRecords, setNumRecords] = useState(filteredData?.length ?? 0);

  useEffect(() => {
    if (dataIsFiltered) {
      setPage(1);
    }
  }, [dataIsFiltered]);

  useEffect(() => {
    if (!filteredData) {
      setRecords([]);
      return;
    }
    let from = (page - 1) * pageSize;
    let to = from + pageSize;
    setNumRecords(filteredData.length);
    setRecords(filteredData.slice(from, to));
  }, [filteredData, page, pageSize]);

  return (
    <DataTable
      height="auto"
      // TODO: you can't use the trackpad to scroll horizontally when the cursor
      // is over a part of the table that is empty, scrolling only works over rows
      // or the scrollbar. Consider making minHeight 0?
      minHeight={rem(300)}
      striped
      highlightOnHover
      withTableBorder
      withColumnBorders
      records={records}
      recordsPerPage={pageSize}
      recordsPerPageOptions={PAGE_SIZES}
      onRecordsPerPageChange={setPageSize}
      totalRecords={numRecords}
      page={page}
      onPageChange={(p) => setPage(p)}
      className="show-white-space scale-table-icons"
      {...otherProps}
    />
  );
}

export default HomeTable;
